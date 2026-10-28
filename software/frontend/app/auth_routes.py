"""Login local y OpenID Connect."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import AuthService
from app.config import settings
from app.oidc import OidcClient
from app.users import UserStore
from app.web_context import web_context

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _request_meta(request: Request) -> tuple[str, str]:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return host, proto


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request, error: Optional[str] = None) -> Any:
    auth: AuthService = request.app.state.auth
    oidc: OidcClient = request.app.state.oidc
    if auth.is_web_authenticated(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "app_name": settings.app_name,
            "app_tagline": "Flota del descheduler",
            "oidc_enabled": oidc.is_configured(),
            "local_enabled": settings.local_auth,
            "error": error,
            "theme": getattr(request.state, "theme", "dark"),
        },
    )


@router.post("/login", include_in_schema=False)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    users: UserStore = request.app.state.users
    user = users.verify(username.strip(), password)
    if user is None:
        return RedirectResponse("/login?error=1", status_code=302)
    request.session["user"] = {
        "email": user.get("email") or f"{user['username']}@local",
        "name": user["username"],
        "sub": user["username"],
        "role": user["role"],
    }
    return RedirectResponse("/", status_code=302)


@router.get("/logout", include_in_schema=False)
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@router.get("/oidc/login", include_in_schema=False)
async def oidc_login(request: Request) -> RedirectResponse:
    oidc: OidcClient = request.app.state.oidc
    if not oidc.is_configured():
        raise HTTPException(status_code=404, detail="OIDC no configurado")
    state = secrets.token_urlsafe(24)
    request.session["oidc_state"] = state
    host, proto = _request_meta(request)
    url = await oidc.auth_url(state, oidc.redirect_uri(host, proto))
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        key="oidc_oauth_state",
        value=state,
        httponly=True,
        secure=settings.session_https_only,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/oidc/callback", include_in_schema=False)
async def oidc_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    oidc: OidcClient = request.app.state.oidc
    expected = request.session.pop("oidc_state", None) or request.cookies.get("oidc_oauth_state")
    if not code or not state or not expected or state != expected:
        raise HTTPException(status_code=400, detail="Estado OIDC invalido. Volvé a ingresar.")
    host, proto = _request_meta(request)
    info = await oidc.user_from_code(code, oidc.redirect_uri(host, proto))
    if info is None:
        return RedirectResponse("/login?error=1", status_code=302)
    users: UserStore = request.app.state.users
    role = oidc.resolve_role(list(info.get("groups") or []))
    stored = users.upsert_oidc(info["sub"], info["email"], info["name"], role)
    request.session["user"] = {
        "email": stored.get("email") or info["email"],
        "name": info["name"],
        "sub": info["sub"],
        "role": stored.get("role") or role,
    }
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("oidc_oauth_state", path="/")
    return response


@router.get("/perfil", response_class=HTMLResponse, include_in_schema=False)
async def profile_page(request: Request) -> Any:
    auth: AuthService = request.app.state.auth
    if auth.web_auth_required and not auth.is_web_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "profile.html",
        {"page": "profile", **web_context(request)},
    )
