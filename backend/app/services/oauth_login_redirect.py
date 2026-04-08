"""HTML response that hands JWT to the SPA via localStorage (same-origin OAuth callback)."""

import json

from fastapi.responses import HTMLResponse


def oauth_web_login_success_response(jwt_token: str) -> HTMLResponse:
    """Store token and send user back to /login; Login.tsx reads `clawith_oauth_login_token`."""
    safe = json.dumps(jwt_token)
    return HTMLResponse(
        content=f"""<!DOCTYPE html><html><head><meta charset="utf-8"/><title>Signing in</title></head><body>
<script>
localStorage.setItem("clawith_oauth_login_token", {safe});
location.replace("/login?oauth_complete=1");
</script>
<noscript><p>Please enable JavaScript to finish signing in, then open the login page.</p></noscript>
</body></html>""",
        media_type="text/html; charset=utf-8",
    )
