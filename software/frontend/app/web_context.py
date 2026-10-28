"""Referencia: contexto Jinja compartido para paginas web.

Copiar/adaptar en app/web.py de la app destino.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.auth import AuthService
from app.config import settings
from app.oidc import OidcClient


def web_context(request: Request) -> dict[str, Any]:
    auth: AuthService = request.app.state.auth
    oidc: OidcClient = request.app.state.oidc
    user = auth.get_session_user(request)
    return {
        "app_name": settings.app_name,
        "app_slug": settings.app_slug,
        "app_version": request.app.version,
        "user_name": user["name"] if user else None,
        "user_email": user["email"] if user else None,
        "user_sub": user["sub"] if user else None,
        "user_role": user["role"] if user else None,
        "is_admin": auth.is_admin(request),
        "can_write": auth.can_write(request),
        "oidc_enabled": oidc.is_configured(),
        "local_enabled": _local_enabled(request),
        "web_auth_required": auth.web_auth_required,
        "api_token_enabled": auth.api_token_enabled,
        "theme": getattr(request.state, "theme", "dark"),
    }


def _local_enabled(request: Request) -> bool:
    return bool(getattr(settings, "local_auth", True))


def require_web_auth(request: Request) -> Optional[RedirectResponse]:
    auth: AuthService = request.app.state.auth
    if auth.web_auth_required and not auth.is_web_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return None
