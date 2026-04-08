import { useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

/** IdPs sometimes configured with a frontend path; forward query string to the real API callback. */
const PROVIDERS = new Set(['wecom', 'feishu', 'dingtalk']);

export default function OAuthFrontendCallbackBridge() {
    const { provider } = useParams();
    const [search] = useSearchParams();

    useEffect(() => {
        const p = provider || '';
        if (!PROVIDERS.has(p)) {
            window.location.replace('/login');
            return;
        }
        const q = search.toString();
        window.location.replace(`/api/auth/${p}/callback${q ? `?${q}` : ''}`);
    }, [provider, search]);

    return (
        <div
            style={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'var(--bg-primary, #0a0a0a)',
                color: 'var(--text-secondary, #a1a1aa)',
                fontSize: '14px',
            }}
        >
            Redirecting…
        </div>
    );
}
