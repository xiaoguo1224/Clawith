"""Feishu (Lark) OAuth and API integration service."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import create_access_token, hash_password
from app.models.user import User

settings = get_settings()

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"
FEISHU_APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
FEISHU_SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"


class FeishuService:
    """Service for Feishu OAuth login and message API."""

    def __init__(self):
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self._app_access_token: str | None = None

    async def get_app_access_token(self) -> str:
        """Get or refresh the app-level access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(FEISHU_APP_TOKEN_URL, json={
                "app_id": self.app_id,
                "app_secret": self.app_secret,
            })
            data = resp.json()
            self._app_access_token = data.get("app_access_token", "")
            return self._app_access_token

    async def exchange_code_for_user(self, code: str) -> dict:
        """Exchange OAuth authorization code for user info.

        Returns dict with: open_id, union_id, user_id, name, email, avatar_url
        """
        app_token = await self.get_app_access_token()

        async with httpx.AsyncClient() as client:
            # Get user access token
            token_resp = await client.post(FEISHU_TOKEN_URL, json={
                "grant_type": "authorization_code",
                "code": code,
            }, headers={"Authorization": f"Bearer {app_token}"})
            token_data = token_resp.json()
            user_access_token = token_data.get("data", {}).get("access_token", "")

            # Get user info
            info_resp = await client.get(FEISHU_USER_INFO_URL, headers={
                "Authorization": f"Bearer {user_access_token}",
            })
            info_data = info_resp.json().get("data", {})

            return {
                "open_id": info_data.get("open_id"),
                "union_id": info_data.get("union_id"),
                "user_id": info_data.get("user_id"),
                "name": info_data.get("name", ""),
                "email": info_data.get("email", ""),
                "avatar_url": info_data.get("avatar_url", ""),
            }

    async def login_or_register(self, db: AsyncSession, feishu_user: dict) -> tuple[User, str]:
        """Login existing user or register new one via Feishu SSO.

        Returns (user, jwt_token)
        """
        open_id = feishu_user["open_id"]

        # Check if user already linked
        result = await db.execute(select(User).where(User.feishu_open_id == open_id))
        user = result.scalar_one_or_none()

        if user:
            # Existing user — update info
            user.avatar_url = feishu_user.get("avatar_url") or user.avatar_url
            token = create_access_token(str(user.id), user.role)
            return user, token

        # New user — create account
        username = feishu_user.get("email", "").split("@")[0] or f"feishu_{open_id[:8]}"
        email = feishu_user.get("email") or f"{username}@feishu.local"

        # Ensure unique username
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            username = f"{username}_{open_id[:6]}"

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(open_id),  # placeholder password
            display_name=feishu_user.get("name", username),
            avatar_url=feishu_user.get("avatar_url"),
            feishu_open_id=open_id,
            feishu_union_id=feishu_user.get("union_id"),
            feishu_user_id=feishu_user.get("user_id"),
        )
        db.add(user)
        await db.flush()

        token = create_access_token(str(user.id), user.role)
        return user, token

    async def bind_feishu(self, db: AsyncSession, user: User, code: str) -> User:
        """Bind Feishu account to existing user."""
        feishu_user = await self.exchange_code_for_user(code)
        user.feishu_open_id = feishu_user["open_id"]
        user.feishu_union_id = feishu_user.get("union_id")
        user.feishu_user_id = feishu_user.get("user_id")
        await db.flush()
        return user

    async def send_message(self, app_id: str, app_secret: str, receive_id: str,
                           msg_type: str, content: str, receive_id_type: str = "open_id") -> dict:
        """Send a message via a specific Feishu bot (per-agent credentials).

        Args:
            app_id: The Feishu app's App ID (per-agent)
            app_secret: The Feishu app's App Secret (per-agent)
            receive_id: Target user's open_id
            msg_type: "text", "interactive", etc.
            content: JSON string of message content
            receive_id_type: "open_id" or "chat_id"
        """
        # Get app access token for this specific agent's bot
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(FEISHU_APP_TOKEN_URL, json={
                "app_id": app_id,
                "app_secret": app_secret,
            })
            app_token = token_resp.json().get("app_access_token", "")

            resp = await client.post(
                f"{FEISHU_SEND_MSG_URL}?receive_id_type={receive_id_type}",
                json={
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": content,
                },
                headers={"Authorization": f"Bearer {app_token}"},
            )
            return resp.json()

    async def resolve_open_id(self, app_id: str, app_secret: str,
                               email: str | None = None, mobile: str | None = None) -> str | None:
        """Resolve a user's open_id for a specific app using email or mobile.

        Each Feishu app gets a unique open_id per user. This method looks up the
        correct open_id for the given app's credentials.
        """
        if not email and not mobile:
            return None

        async with httpx.AsyncClient() as client:
            token_resp = await client.post(FEISHU_APP_TOKEN_URL, json={
                "app_id": app_id,
                "app_secret": app_secret,
            })
            app_token = token_resp.json().get("app_access_token", "")

            body: dict = {}
            if email:
                body["emails"] = [email]
            if mobile:
                body["mobiles"] = [mobile]

            resp = await client.post(
                "https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id",
                json=body,
                headers={"Authorization": f"Bearer {app_token}"},
                params={"user_id_type": "open_id"},
            )
            data = resp.json()
            if data.get("code") != 0:
                return None

            user_list = data.get("data", {}).get("user_list", [])
            for u in user_list:
                oid = u.get("user_id")
                if oid:
                    return oid
            return None

    async def send_approval_card(self, app_id: str, app_secret: str,
                                  creator_open_id: str, agent_name: str,
                                  action_type: str, details: str, approval_id: str) -> dict:
        """Send an interactive approval card to the agent creator via Feishu."""
        import json
        card_content = json.dumps({
            "type": "template",
            "data": {
                "template_id": "",  # Use custom card
                "template_variable": {
                    "agent_name": agent_name,
                    "action_type": action_type,
                    "details": details,
                    "approval_id": approval_id,
                }
            }
        })
        # Simplified — in production, use Feishu interactive card JSON
        text_content = json.dumps({
            "text": f"🔴 [{agent_name}] 请求审批\n操作: {action_type}\n详情: {details}\n\n请在 Clawith 平台审批。"
        })
        return await self.send_message(app_id, app_secret, creator_open_id, "text", text_content)


feishu_service = FeishuService()
