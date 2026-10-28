from __future__ import annotations

import hmac
from typing import Optional

from fastapi import HTTPException, Request

from app.config import Settings

ROLE_ADMIN = "admin"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def web_auth_required(self) -> bool:
        return True

    @property
    def api_token_enabled(self) -> bool:
        return bool(self.settings.api_token)

    def get_session_user(self, request: Request) -> Optional[dict[str, str]]:
        user = request.session.get("user")
        if isinstance(user, dict) and (user.get("email") or user.get("name")):
            return {
                "email": str(user.get("email") or ""),
                "name": str(user.get("name") or user.get("email") or ""),
                "sub": str(user.get("sub") or user.get("email") or ""),
                "role": str(user.get("role") or "readonly"),
            }
        return None

    def is_web_authenticated(self, request: Request) -> bool:
        return self.get_session_user(request) is not None

    def is_admin(self, request: Request) -> bool:
        user = self.get_session_user(request)
        return user is not None and user.get("role") == ROLE_ADMIN

    def can_write(self, request: Request) -> bool:
        return self.is_admin(request)

    def validate_api_token(self, authorization: Optional[str], x_api_token: Optional[str] = None) -> bool:
        expected = (self.settings.api_token or "").strip()
        if not expected:
            return False
        token = self._extract_bearer(authorization) or (x_api_token or "").strip()
        if not token:
            return False
        return hmac.compare_digest(token, expected)

    def require_web_or_api(
        self,
        request: Request,
        authorization: Optional[str] = None,
        x_api_token: Optional[str] = None,
    ) -> None:
        if self.is_web_authenticated(request):
            return
        if self.validate_api_token(authorization, x_api_token):
            return
        raise HTTPException(status_code=401, detail="No autenticado")

    @staticmethod
    def _extract_bearer(authorization: Optional[str]) -> str:
        if not authorization:
            return ""
        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return ""
        return parts[1].strip()
