"""Build per-tenant OAuth / IdP authorization URLs for web login (Feishu, DingTalk, WeCom, generic OAuth2)."""

from __future__ import annotations

import uuid
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import IdentityProvider

from app.services.identity_provider_pick import pick_preferred_identity_provider
from app.services.oauth_redirect_uri import resolve_oauth_redirect_uri


def _dedupe_identity_providers_for_login_urls(providers: list) -> list:
    """One login button per vendor channel (feishu / dingtalk / wecom).

    Tenants may accidentally have duplicate rows (e.g. old platform default + new config);
    all oauth2 rows are kept so multiple generic IdPs remain possible.
    """
    feishu = [p for p in providers if p.provider_type == "feishu"]
    dingtalk = [p for p in providers if p.provider_type == "dingtalk"]
    wecom = [p for p in providers if p.provider_type == "wecom"]
    oauth2 = [p for p in providers if p.provider_type == "oauth2"]
    rest = [
        p
        for p in providers
        if p.provider_type not in ("feishu", "dingtalk", "wecom", "oauth2")
    ]

    def pick_one(candidates: list):
        chosen = pick_preferred_identity_provider(candidates)
        return [chosen] if chosen else []

    return pick_one(feishu) + pick_one(dingtalk) + pick_one(wecom) + oauth2 + rest


async def build_oauth_login_urls_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    public_base: str,
    state: str,
) -> list[dict]:
    """Return [{provider_type, name, url}, ...] for IdPs with OAuth/scan login enabled."""
    query = select(IdentityProvider).where(
        IdentityProvider.is_active == True,
        IdentityProvider.sso_login_enabled == True,
    )
    if tenant_id:
        query = query.where(IdentityProvider.tenant_id == tenant_id)
    else:
        query = query.where(IdentityProvider.tenant_id.is_(None))

    result = await db.execute(query)
    providers = _dedupe_identity_providers_for_login_urls(list(result.scalars().all()))

    auth_urls: list[dict] = []
    tid = str(tenant_id) if tenant_id else None

    for p in providers:
        cfg = p.config or {}
        if p.provider_type == "feishu":
            app_id = cfg.get("app_id")
            if app_id:
                redir = resolve_oauth_redirect_uri(cfg, public_base, "feishu")
                url = f"https://open.feishu.cn/open-apis/authen/v1/index?app_id={app_id}&redirect_uri={quote(redir)}&state={state}"
                auth_urls.append({"provider_type": "feishu", "name": p.name, "url": url})

        elif p.provider_type == "dingtalk":
            from app.services.auth_registry import auth_provider_registry

            auth_provider = await auth_provider_registry.get_provider(db, "dingtalk", tid)
            if auth_provider:
                redir = resolve_oauth_redirect_uri(auth_provider.config, public_base, "dingtalk")
                url = await auth_provider.get_authorization_url(redir, state)
                auth_urls.append({"provider_type": "dingtalk", "name": p.name, "url": url})

        elif p.provider_type == "wecom":
            corp_id = cfg.get("corp_id")
            agent_id = cfg.get("agent_id")
            if corp_id and agent_id:
                redir = resolve_oauth_redirect_uri(cfg, public_base, "wecom")
                # qrConnect: works in desktop browsers (scan QR). OAuth2 authorize + snsapi_privateinfo
                # returns user_ticket for getuserdetail (mobile/email) but only opens inside WeCom client
                # — desktop Chrome shows "请在企业微信客户端打开链接" (doc 91022 / 91023).
                if cfg.get("wecom_oauth_privateinfo"):
                    url = (
                        "https://open.weixin.qq.com/connect/oauth2/authorize"
                        f"?appid={corp_id}"
                        f"&redirect_uri={quote(redir, safe='')}"
                        "&response_type=code"
                        "&scope=snsapi_privateinfo"
                        f"&agentid={agent_id}"
                        f"&state={quote(state, safe='')}"
                        "#wechat_redirect"
                    )
                else:
                    url = (
                        "https://open.work.weixin.qq.com/wwopen/sso/qrConnect"
                        f"?appid={corp_id}"
                        f"&agentid={agent_id}"
                        f"&redirect_uri={quote(redir, safe='')}"
                        f"&state={quote(state, safe='')}"
                    )
                auth_urls.append({"provider_type": "wecom", "name": p.name, "url": url})

        elif p.provider_type == "oauth2":
            cid = cfg.get("app_id") or cfg.get("client_id")
            if cfg.get("authorize_url") and cfg.get("token_url") and cfg.get("user_info_url") and cid:
                from app.services.auth_registry import auth_provider_registry

                auth_provider = await auth_provider_registry.get_provider(db, "oauth2", tid)
                if auth_provider:
                    redir = resolve_oauth_redirect_uri(auth_provider.config, public_base, "oauth2")
                    url = await auth_provider.get_authorization_url(redir, state)
                    auth_urls.append({"provider_type": "oauth2", "name": p.name, "url": url})

    return auth_urls
