import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../stores';
import { authApi, tenantApi } from '../services/api';

export default function Login() {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const setAuth = useAuthStore((s) => s.setAuth);
    const [isRegister, setIsRegister] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [tenants, setTenants] = useState<{ id: string; name: string; slug: string }[]>([]);

    const [form, setForm] = useState({
        username: '',
        password: '',
        email: '',
        display_name: '',
        tenant_id: '',
    });

    // Load available companies when switching to register mode
    useEffect(() => {
        if (isRegister && tenants.length === 0) {
            tenantApi.listPublic().then(setTenants).catch(() => { });
        }
    }, [isRegister]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            let res;
            if (isRegister) {
                if (!form.tenant_id) {
                    setError(t('auth.selectCompany'));
                    setLoading(false);
                    return;
                }
                res = await authApi.register(form);
            } else {
                res = await authApi.login({ username: form.username, password: form.password });
            }
            setAuth(res.user, res.access_token);
            navigate('/');
        } catch (err: any) {
            setError(err.message || t('common.error'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-title">Clawith</div>
                <div className="login-subtitle">{t('app.tagline')}</div>

                {error && (
                    <div style={{ background: 'var(--error-subtle)', color: 'var(--error)', padding: '8px 12px', borderRadius: '6px', fontSize: '13px', marginBottom: '16px' }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label className="form-label">{t('auth.username')}</label>
                        <input
                            className="form-input"
                            value={form.username}
                            onChange={(e) => setForm({ ...form, username: e.target.value })}
                            required
                            autoFocus
                        />
                    </div>

                    {isRegister && (
                        <>
                            <div className="form-group">
                                <label className="form-label">{t('auth.email')}</label>
                                <input
                                    className="form-input"
                                    type="email"
                                    value={form.email}
                                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">{t('auth.displayName')}</label>
                                <input
                                    className="form-input"
                                    value={form.display_name}
                                    onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label">{t('auth.selectCompany')}</label>
                                <select
                                    className="form-input"
                                    value={form.tenant_id}
                                    onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
                                    required
                                    style={{ height: '38px', cursor: 'pointer' }}
                                >
                                    <option value="">{t('auth.selectCompanyPlaceholder')}</option>
                                    {tenants.map((t) => (
                                        <option key={t.id} value={t.id}>{t.name}</option>
                                    ))}
                                </select>
                            </div>
                        </>
                    )}

                    <div className="form-group">
                        <label className="form-label">{t('auth.password')}</label>
                        <input
                            className="form-input"
                            type="password"
                            value={form.password}
                            onChange={(e) => setForm({ ...form, password: e.target.value })}
                            required
                        />
                    </div>

                    <button className="btn btn-primary" type="submit" disabled={loading}
                        style={{ width: '100%', height: '40px', fontSize: '14px' }}>
                        {loading ? t('common.loading') : isRegister ? t('auth.register') : t('auth.login')}
                    </button>
                </form>



                <div style={{ textAlign: 'center', marginTop: '20px', fontSize: '13px', color: 'var(--text-tertiary)' }}>
                    {isRegister ? t('auth.hasAccount') : t('auth.noAccount')}{' '}
                    <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(!isRegister); setError(''); }}>
                        {isRegister ? t('auth.goLogin') : t('auth.goRegister')}
                    </a>
                </div>
            </div>
        </div>
    );
}
