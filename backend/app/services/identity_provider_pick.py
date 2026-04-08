"""When multiple IdentityProvider rows exist for the same tenant + type, pick one consistently."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.identity import IdentityProvider


def pick_preferred_identity_provider(candidates: list[IdentityProvider]) -> IdentityProvider | None:
    """Prefer a row with custom oauth_redirect_uri, then newest updated_at, then stable id."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    _epoch = datetime.min.replace(tzinfo=timezone.utc)

    def sort_key(p: IdentityProvider) -> tuple:
        cfg = p.config or {}
        has_custom = bool((cfg.get("oauth_redirect_uri") or cfg.get("redirect_uri") or "").strip())
        ua = p.updated_at or p.created_at or _epoch
        return (has_custom, ua, str(p.id))

    return max(candidates, key=sort_key)
