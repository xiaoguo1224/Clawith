import { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores';
import { authApi, tenantApi, fetchJson } from '../services/api';
import type { TokenResponse } from '../types';

export default function Login() {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const invitationCode = searchParams.get('code');
    const invitedEmail = searchParams.get('email') || '';
    const setAuth = useAuthStore((s) => s.setAuth);
    // Default to register if there's an invitation code — will be overridden after email check
    const [isRegister, setIsRegister] = useState(!!invitationCode);
    const [error, setError] = useState('');
    const [successMessage, setSuccessMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [checkingEmail, setCheckingEmail] = useState(!!invitationCode && !!invitedEmail);
    const [tenant, setTenant] = useState<any>(null);
    const [resolving, setResolving] = useState(true);
    const [oauthProviders, setOauthProviders] = useState<any[]>([]);
    const [oauthLoading, setOauthLoading] = useState(false);
    const [oauthError, setOauthError] = useState('');
    const [oauthCompanyDirectory, setOauthCompanyDirectory] = useState<Array<{ id: string; name: string; slug: string }>>([]);
    const [oauthDirectoryLoading, setOauthDirectoryLoading] = useState(false);
    const [selectedOauthTenantId, setSelectedOauthTenantId] = useState('');
    const [tenantSelection, setTenantSelection] = useState<any[] | null>(null);

    const [form, setForm] = useState({
        login_identifier: invitedEmail,  // Pre-fill invited email if present
        password: '',
        tenant_id: '',
    });

    // OAuth callback: IdP returns to API, which sets clawith_oauth_login_token and redirects here.
    useEffect(() => {
        if (searchParams.get('oauth_complete') !== '1') return;
        let cancelled = false;
        (async () => {
            const tok = localStorage.getItem('clawith_oauth_login_token');
            localStorage.removeItem('clawith_oauth_login_token');
            if (!tok) {
                if (!cancelled) {
                    setError(t('auth.oauthMissingToken', 'Sign-in could not complete. Please try again.'));
                    navigate('/login', { replace: true });
                }
                return;
            }
            localStorage.setItem('token', tok);
            try {
                const me = await authApi.me();
                if (cancelled) return;
                setAuth(me, tok);
                navigate('/', { replace: true });
            } catch {
                if (!cancelled) {
                    localStorage.removeItem('token');
                    setError(t('auth.oauthSessionFailed', 'Could not load your profile. Please try again.'));
                    navigate('/login', { replace: true });
                }
            }
        })();
        return () => { cancelled = true; };
    }, [searchParams, navigate, setAuth, t]);

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', 'dark');

        // If arriving via invitation link with email, check whether the email is already registered
        // to decide whether to show login or register form.
        if (invitationCode && invitedEmail) {
            setCheckingEmail(true);
            fetch('/api/enterprise/check-email-exists', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: invitedEmail }),
            })
                .then(r => r.json())
                .then((res: { exists: boolean }) => {
                    // If email already registered → show login form; otherwise show register form
                    setIsRegister(!res.exists);
                })
                .catch(() => {
                    // On error, fall back to register form (safe default)
                    setIsRegister(true);
                })
                .finally(() => setCheckingEmail(false));
        }

        // Resolve tenant by domain (for OAuth buttons on company-specific host)
        const domain = window.location.host;
        if (domain.startsWith('localhost') || domain.startsWith('127.0.0.1')) {
            setResolving(false);
            return;
        }

        tenantApi.resolveByDomain(domain)
            .then(res => {
                if (res) {
                    setTenant(res);
                }
            })
            .catch(() => { })
            .finally(() => setResolving(false));
    }, []);

    useEffect(() => {
        if (isRegister) return;
        if (tenant?.sso_enabled && tenant?.id) return;
        let cancelled = false;
        setOauthDirectoryLoading(true);
        tenantApi.publicOauthDirectory()
            .then((list) => {
                if (!cancelled) setOauthCompanyDirectory(list || []);
            })
            .catch(() => {
                if (!cancelled) setOauthCompanyDirectory([]);
            })
            .finally(() => {
                if (!cancelled) setOauthDirectoryLoading(false);
            });
        return () => { cancelled = true; };
    }, [isRegister, tenant?.id, tenant?.sso_enabled]);

    useEffect(() => {
        let cancelled = false;
        if (isRegister) {
            setOauthProviders([]);
            setOauthError('');
            return;
        }
        const tid =
            tenant?.sso_enabled && tenant?.id
                ? String(tenant.id)
                : selectedOauthTenantId;
        if (!tid) {
            setOauthProviders([]);
            setOauthLoading(false);
            setOauthError('');
            return;
        }

        setOauthLoading(true);
        setOauthError('');

        fetchJson<any[]>(`/oauth/login-options?tenant_id=${encodeURIComponent(tid)}`)
            .then((providers) => {
                if (cancelled) return;
                setOauthProviders(providers || []);
            })
            .catch(() => {
                if (cancelled) return;
                setOauthError(t('auth.oauthLoadFailed', 'Failed to load sign-in options.'));
                setOauthProviders([]);
            })
            .finally(() => {
                if (cancelled) return;
                setOauthLoading(false);
            });

        return () => { cancelled = true; };
    }, [tenant?.id, tenant?.sso_enabled, isRegister, selectedOauthTenantId, t]);

    const dedicatedOauthTenant = !!(tenant?.sso_enabled && tenant?.id);
    const showOauthCompanyPicker = !isRegister && !dedicatedOauthTenant && (oauthDirectoryLoading || oauthCompanyDirectory.length > 0);
    const effectiveOauthTenantId = dedicatedOauthTenant && tenant?.id ? String(tenant.id) : selectedOauthTenantId;
    const showOauthButtons = !isRegister && !!effectiveOauthTenantId;

    const toggleLang = () => {
        i18n.changeLanguage(i18n.language === 'zh' ? 'en' : 'zh');
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setSuccessMessage('');
        setLoading(true);

        try {
            if (isRegister) {
                const regRes = await authApi.register({
                    username: form.login_identifier.split('@')[0],
                    email: form.login_identifier,
                    password: form.password,
                    display_name: form.login_identifier.split('@')[0],
                    ...(invitationCode ? { invitation_code: invitationCode } : {})
                });
                // Save authentication state for company selection (user not active yet)
                if (regRes.access_token && regRes.user) {
                    setAuth(regRes.user, regRes.access_token);
                }
                // Redirect based on whether company setup is needed
                if (regRes.needs_company_setup === false) {
                    navigate('/verify-email', { state: { fromRegister: true, email: regRes.email } });
                } else {
                    navigate('/setup-company', { state: { fromRegister: true, email: regRes.email } });
                }
                return;
            } else {
                const res = await authApi.login({
                    login_identifier: form.login_identifier,
                    password: form.password,
                    // Only pass tenant_id for dedicated SSO subdomain login (not IP-mode SSO).
                    // IP-mode SSO resolves a tenant for SSO buttons only and must NOT constrain
                    // password-based login to that tenant (it would reject users from other tenants).
                    ...(tenant?.id && tenant.sso_domain && !tenant.sso_domain.match(/^https?:\/\/\d{1,3}(\.\d{1,3}){3}(:\d+)?$/)
                        ? { tenant_id: tenant.id }
                        : {}
                    ),
                });

                // Check if multi-tenant selection is needed
                if ('requires_tenant_selection' in res && res.requires_tenant_selection) {
                    setTenantSelection(res.tenants);
                    setLoading(false);
                    return;
                }

                const tokenRes = res as TokenResponse;
                setAuth(tokenRes.user, tokenRes.access_token);

                // If the user arrived via an invitation link, join the invited company
                // before redirecting. The /tenants/join endpoint handles:
                // - Existing user with no tenant → assigns the tenant directly
                // - Existing user with a tenant → creates a new User record for the new tenant
                //   and returns a new access_token scoped to that tenant.
                if (invitationCode) {
                    try {
                        const joinRes = await tenantApi.join(invitationCode);
                        if (joinRes?.access_token) {
                            // Store the new tenant-scoped token first so that
                            // the subsequent /auth/me call uses the correct context.
                            localStorage.setItem('token', joinRes.access_token);
                            const meRes = await authApi.me();
                            setAuth(meRes, joinRes.access_token);
                        }
                        navigate('/');
                        return;
                    } catch (joinErr: any) {
                        // If joining fails (code already used, code invalid, already a member),
                        // just continue into the user's existing company — don't block login.
                        console.warn('[invitation] join failed, entering original company:', joinErr.message);
                    }
                }

                if (tokenRes.user && !tokenRes.user.tenant_id) {
                    navigate('/setup-company');
                } else {
                    navigate('/');
                }
            }
        } catch (err: any) {
            // Handle structured verification error
            if (err.detail?.needs_verification) {
                navigate('/verify-email', { 
                    state: { 
                        fromRegister: false, 
                        email: err.detail.email || form.login_identifier 
                    } 
                });
                return;
            }

            const msg = err.message || '';
            if (msg && msg !== 'Failed to fetch' && !msg.includes('NetworkError') && !msg.includes('ERR_CONNECTION')) {
                if (msg.includes('company has been disabled')) {
                    setError(t('auth.companyDisabled'));
                } else if (msg.includes('Invalid credentials')) {
                    setError(t('auth.invalidCredentials'));
                } else if (msg.includes('Account is disabled')) {
                    setError(t('auth.accountDisabled'));
                } else if (msg.includes('does not belong to this organization')) {
                    setError(t('auth.notInOrganization', 'This account does not belong to this organization.'));
                } else if (msg.includes('500') || msg.includes('Internal Server Error')) {
                    setError(t('auth.serverStarting'));
                } else if (msg.includes('Email already registered') || msg.includes('该邮箱已注册')) {
                    setError(t('auth.emailAlreadyRegistered', '该邮箱已注册，请直接登录'));
                } else {
                    setError(msg);
                }
            } else {
                setError(t('auth.serverUnreachable'));
            }
        } finally {
            setLoading(false);
        }
    };

    const handleTenantSelect = async (tenantId: string) => {
        setForm(f => ({ ...f, tenant_id: tenantId }));
        setTenantSelection(null);
        setError('');
        setLoading(true);

        try {
            const res = await authApi.login({
                login_identifier: form.login_identifier,
                password: form.password,
                tenant_id: tenantId,
            });

            // Should not get multi-tenant response when tenant_id is provided
            if ('requires_tenant_selection' in res && res.requires_tenant_selection) {
                setTenantSelection(res.tenants);
                setLoading(false);
                return;
            }

            const tokenRes = res as TokenResponse;
            setAuth(tokenRes.user, tokenRes.access_token);
            if (tokenRes.user && !tokenRes.user.tenant_id) {
                navigate('/setup-company');
            } else {
                navigate('/');
            }
        } catch (err: any) {
            const msg = err.message || '';
            setError(msg || t('auth.loginFailed', 'Login failed'));
        } finally {
            setLoading(false);
        }
    };

    const oauthMeta: Record<string, { label: string; icon: string }> = {
        feishu: { label: 'Feishu', icon: '/feishu.png' },
        dingtalk: { label: 'DingTalk', icon: '/dingtalk.png' },
        wecom: { label: 'WeCom', icon: '/wecom.png' },
        oauth2: { label: 'OAuth 2.0', icon: '' },
    };

    return (
        <div className="login-page">
            {/* ── Left: Branding Panel ── */}
            <div className="login-hero">
                <div className="login-hero-bg" />
                <div className="login-hero-content">
                    <div className="login-hero-badge">
                        <span className="login-hero-badge-dot" />
                        {t('login.hero.badge')}
                    </div>
                    <h1 className="login-hero-title">
                        {t('login.hero.title')}<br />
                        <span style={{ fontSize: '0.65em', fontWeight: 600, opacity: 0.85 }}>{t('login.hero.subtitle')}</span>
                    </h1>
                    <p className="login-hero-desc" dangerouslySetInnerHTML={{ __html: t('login.hero.description') }} />
                    <div className="login-hero-features">
                        <div className="login-hero-feature">
                            <span className="login-hero-feature-icon">🤖</span>
                            <div>
                                <div className="login-hero-feature-title">{t('login.hero.features.multiAgent.title')}</div>
                                <div className="login-hero-feature-desc">{t('login.hero.features.multiAgent.description')}</div>
                            </div>
                        </div>
                        <div className="login-hero-feature">
                            <span className="login-hero-feature-icon">🧠</span>
                            <div>
                                <div className="login-hero-feature-title">{t('login.hero.features.persistentMemory.title')}</div>
                                <div className="login-hero-feature-desc">{t('login.hero.features.persistentMemory.description')}</div>
                            </div>
                        </div>
                        <div className="login-hero-feature">
                            <span className="login-hero-feature-icon">🏛️</span>
                            <div>
                                <div className="login-hero-feature-title">{t('login.hero.features.agentPlaza.title')}</div>
                                <div className="login-hero-feature-desc">{t('login.hero.features.agentPlaza.description')}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Right: Form Panel ── */}
            <div className="login-form-panel">
                {/* Language Switcher */}
                <div style={{
                    position: 'absolute', top: '16px', right: '16px',
                    cursor: 'pointer', fontSize: '13px', color: 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', gap: '4px',
                    padding: '6px 12px', borderRadius: '8px',
                    background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                    zIndex: 101,
                }} onClick={toggleLang}>
                    🌐
                </div>

                <div className="login-form-wrapper">
                    {checkingEmail ? (
                        // While resolving invitation email, show a minimal loading indicator
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '200px', gap: '16px' }}>
                            <span className="login-spinner" style={{ width: 24, height: 24 }} />
                            <span style={{ fontSize: '13px', color: 'var(--text-tertiary)' }}>
                                {t('auth.checkingInvitation', 'Checking invitation...')}
                            </span>
                        </div>
                    ) : (
                    <>
                    <div className="login-form-header">
                        <div className="login-form-logo"><img src="/logo-black.png" className="login-logo-img" alt="" style={{ width: 28, height: 28, marginRight: 8, verticalAlign: 'middle' }} />Clawith</div>
                        <h2 className="login-form-title">
                            {isRegister ? t('auth.register') : t('auth.login')}
                        </h2>
                        <p className="login-form-subtitle">
                            {isRegister ? t('auth.subtitleRegister') : t('auth.subtitleLogin')}
                        </p>
                    </div>

                    {error && (
                        <div className="login-error">
                            <span>⚠</span> {error}
                        </div>
                    )}

                    {successMessage && (
                        <div className="login-success" style={{
                            background: 'rgba(34, 197, 94, 0.1)',
                            color: '#16a34a',
                            padding: '12px 16px',
                            borderRadius: '8px',
                            marginBottom: '16px',
                            fontSize: '14px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            border: '1px solid rgba(34, 197, 94, 0.2)',
                        }}>
                            <span>✓</span> {successMessage}
                        </div>
                    )}

                    {showOauthCompanyPicker && (
                        <div style={{ marginBottom: '16px' }}>
                            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                                {t('auth.oauthSelectCompany', 'Company')}
                            </label>
                            <select
                                style={{
                                    width: '100%',
                                    padding: '12px 14px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border-subtle)',
                                    background: 'var(--bg-secondary)',
                                    color: 'var(--text-primary)',
                                    fontSize: '14px',
                                }}
                                value={selectedOauthTenantId}
                                onChange={(e) => setSelectedOauthTenantId(e.target.value)}
                                disabled={oauthDirectoryLoading}
                            >
                                <option value="">
                                    {oauthDirectoryLoading
                                        ? t('auth.oauthDirectoryLoading', 'Loading companies…')
                                        : t('auth.oauthSelectCompanyPlaceholder', '— Select your company —')}
                                </option>
                                {oauthCompanyDirectory.map((c) => (
                                    <option key={c.id} value={c.id}>{c.name}</option>
                                ))}
                            </select>
                            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '6px' }}>
                                {t('auth.oauthSelectCompanyHint', 'Then scan with Feishu, DingTalk, WeCom, or your OAuth provider.')}
                            </div>
                        </div>
                    )}

                    {showOauthButtons && (
                        <div style={{ marginBottom: '24px' }}>
                            {dedicatedOauthTenant && tenant && (
                                <div style={{
                                    padding: '16px', borderRadius: '12px', background: 'rgba(59,130,246,0.08)',
                                    border: '1px solid rgba(59,130,246,0.15)', marginBottom: '16px',
                                    textAlign: 'center'
                                }}>
                                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--accent-primary)', marginBottom: '4px' }}>
                                        {tenant.name}
                                    </div>
                                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                                        {t('auth.oauthNotice', 'Scan to sign in with your work account.')}
                                    </div>
                                </div>
                            )}

                            {oauthLoading && (
                                <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '12px' }}>
                                    {t('auth.oauthLoading', 'Loading sign-in options…')}
                                </div>
                            )}

                            {!oauthLoading && oauthProviders.length > 0 && (
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
                                    {oauthProviders.map((p, idx) => {
                                        const meta = oauthMeta[p.provider_type] || { label: p.name || p.provider_type, icon: '' };
                                        return (
                                            <button
                                                key={`${p.provider_type}-${p.name || ''}-${idx}`}
                                                type="button"
                                                className="login-submit"
                                                style={{
                                                    background: 'var(--bg-secondary)',
                                                    color: 'var(--text-primary)',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    gap: '10px',
                                                    border: '1px solid var(--border-subtle)',
                                                }}
                                                onClick={() => { window.location.href = p.url; }}
                                            >
                                                {meta.icon ? (
                                                    <img src={meta.icon} alt={meta.label} width={18} height={18} style={{ borderRadius: '4px' }} />
                                                ) : (
                                                    <span style={{ width: 18, height: 18, borderRadius: 4, background: 'var(--bg-tertiary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 10 }}>
                                                        {(meta.label || '').slice(0, 1).toUpperCase()}
                                                    </span>
                                                )}
                                                {meta.label || p.name || p.provider_type}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}

                            {!oauthLoading && oauthProviders.length === 0 && (
                                <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '12px' }}>
                                    {oauthError || t('auth.oauthNoProviders', 'No sign-in methods configured.')}
                                </div>
                            )}

                            <div style={{
                                display: 'flex', alignItems: 'center', gap: '12px',
                                margin: '20px 0', color: 'var(--text-tertiary)', fontSize: '11px'
                            }}>
                                <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
                                {t('auth.or', 'or')}
                                <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
                            </div>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="login-form">
                        <div className="login-field">
                            <label>{t('auth.email')}</label>
                            <input
                                type="email"
                                value={form.login_identifier}
                                onChange={(e) => setForm({ ...form, login_identifier: e.target.value })}
                                required
                                autoFocus
                                placeholder={t('auth.emailPlaceholder')}
                            />
                        </div>

                        <div className="login-field">
                            <label>{t('auth.password')}</label>
                            <input
                                type="password"
                                value={form.password}
                                onChange={(e) => setForm({ ...form, password: e.target.value })}
                                required
                                placeholder={t('auth.passwordPlaceholder')}
                            />
                        </div>

                        {!isRegister && (
                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '-4px', marginBottom: '8px' }}>
                                <Link
                                    to="/forgot-password"
                                    style={{ fontSize: '13px', color: 'var(--accent-primary)', textDecoration: 'none' }}
                                >
                                    {t('auth.forgotPassword', 'Forgot password?')}
                                </Link>
                            </div>
                        )}

                        <button className="login-submit" type="submit" disabled={loading}>
                            {loading ? (
                                <span className="login-spinner" />
                            ) : (
                                <>
                                    {isRegister ? t('auth.register') : t('auth.login')}
                                    <span style={{ marginLeft: '6px' }}>→</span>
                                </>
                            )}
                        </button>
                    </form>

                    {/* Multi-tenant selection modal */}
                    {tenantSelection && (
                        <div style={{
                            position: 'fixed',
                            top: 0, left: 0, right: 0, bottom: 0,
                            background: 'rgba(5, 5, 8, 0.82)',
                            backdropFilter: 'blur(8px)',
                            WebkitBackdropFilter: 'blur(8px)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 2000,
                        }}>
                            {/* Dark glass card — stands out via border + shadow, not color inversion */}
                            <div style={{
                                background: '#161620',
                                borderRadius: '16px',
                                padding: '32px',
                                maxWidth: '400px',
                                width: '90%',
                                border: '1px solid rgba(255, 255, 255, 0.12)',
                                boxShadow: '0 0 0 1px rgba(255,255,255,0.04), 0 32px 80px rgba(0,0,0,0.7)',
                            }}>
                                <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px', color: 'rgba(255,255,255,0.95)' }}>
                                    {t('auth.selectOrganization', '选择公司')}
                                </h3>
                                <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.42)', marginBottom: '20px', lineHeight: '1.5' }}>
                                    {t('auth.multiTenantPrompt', '该邮箱对应多个公司，请选择要登录的公司：')}
                                </p>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                    {tenantSelection.map((tenant: any) => (
                                        <button
                                            key={tenant.tenant_id}
                                            onClick={() => handleTenantSelect(tenant.tenant_id)}
                                            style={{
                                                padding: '12px 16px',
                                                borderRadius: '10px',
                                                border: '1px solid rgba(255,255,255,0.09)',
                                                background: 'rgba(255,255,255,0.05)',
                                                color: 'rgba(255,255,255,0.88)',
                                                fontSize: '14px',
                                                fontWeight: 500,
                                                cursor: 'pointer',
                                                textAlign: 'left',
                                                transition: 'background 0.15s, border-color 0.15s',
                                            }}
                                            onMouseEnter={e => {
                                                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.10)';
                                                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.20)';
                                            }}
                                            onMouseLeave={e => {
                                                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)';
                                                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.09)';
                                            }}
                                        >
                                            {tenant.tenant_name} {tenant.tenant_slug && `(${tenant.tenant_slug})`}
                                        </button>
                                    ))}
                                    {/* Create or Join Organization */}
                                    <button
                                        onClick={async () => {
                                            // Log in with the first tenant to get a valid token, then redirect to company setup
                                            try {
                                                setLoading(true);
                                                const firstTenant = tenantSelection[0];
                                                const res = await authApi.login({
                                                    login_identifier: form.login_identifier,
                                                    password: form.password,
                                                    tenant_id: firstTenant.tenant_id,
                                                });
                                                const tokenRes = res as TokenResponse;
                                                setAuth(tokenRes.user, tokenRes.access_token);
                                                setTenantSelection(null);
                                                navigate('/setup-company?from=tenant-selection');
                                            } catch (err: any) {
                                                setError(err.message || 'Failed');
                                                setTenantSelection(null);
                                            } finally {
                                                setLoading(false);
                                            }
                                        }}
                                        style={{
                                            padding: '12px 16px',
                                            borderRadius: '10px',
                                            border: '1px dashed rgba(255,255,255,0.15)',
                                            background: 'transparent',
                                            color: 'rgba(255,255,255,0.38)',
                                            fontSize: '14px',
                                            cursor: 'pointer',
                                            textAlign: 'left',
                                            transition: 'border-color 0.15s, color 0.15s',
                                        }}
                                        onMouseEnter={e => {
                                            (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.28)';
                                            (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.6)';
                                        }}
                                        onMouseLeave={e => {
                                            (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.15)';
                                            (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.38)';
                                        }}
                                    >
                                        {t('auth.createOrJoinOrganization', 'Create or Join Organization')}
                                    </button>
                                </div>
                                <button
                                    onClick={() => setTenantSelection(null)}
                                    style={{
                                        marginTop: '16px',
                                        padding: '10px 16px',
                                        borderRadius: '10px',
                                        border: '1px solid rgba(255,255,255,0.07)',
                                        background: 'rgba(255,255,255,0.04)',
                                        color: 'rgba(255,255,255,0.5)',
                                        fontSize: '14px',
                                        fontWeight: 500,
                                        cursor: 'pointer',
                                        width: '100%',
                                        transition: 'background 0.15s, color 0.15s',
                                    }}
                                    onMouseEnter={e => {
                                        (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)';
                                        (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.7)';
                                    }}
                                    onMouseLeave={e => {
                                        (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.04)';
                                        (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.5)';
                                    }}
                                >
                                    {t('common.cancel', 'Cancel')}
                                </button>
                            </div>
                        </div>
                    )}

                    <div className="login-switch">
                        {isRegister ? t('auth.hasAccount') : t('auth.noAccount')}{' '}
                        <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(!isRegister); setError(''); }}>
                            {isRegister ? t('auth.goLogin') : t('auth.goRegister')}
                        </a>
                    </div>
                    </>
                    )}
                </div>
            </div>
        </div>
    );
}
