from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AuthService
from app.auth_routes import router as auth_router
from app.backend_client import BackendClient
from app.config import settings
from app.logging_config import configure_logging
from app.oidc import OidcClient
from app.service_user import ensure_service_user
from app.users import UserStore
from app.web import router as web_router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    users = UserStore(settings.data_dir / "users.db")
    ensure_service_user(users)
    app.state.users = users
    app.state.auth = AuthService(settings)
    app.state.oidc = OidcClient(settings)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.session_https_only,
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(auth_router)
app.include_router(web_router)


@app.middleware("http")
async def load_theme(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static") or path.startswith("/api") or path in {"/health", "/sw.js"}:
        request.state.theme = "dark"
        return await call_next(request)
    theme = "dark"
    try:
        payload = await BackendClient().get_json("/api/v1/appearance")
        if payload.get("theme") == "light":
            theme = "light"
    except Exception:  # noqa: BLE001
        theme = "dark"
    request.state.theme = theme
    return await call_next(request)


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript; charset=utf-8",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE"], include_in_schema=False)
async def proxy_api(path: str, request: Request) -> Response:
    auth: AuthService = request.app.state.auth
    authorization = request.headers.get("authorization")
    x_api_token = request.headers.get("x-api-token")
    session_ok = auth.is_web_authenticated(request)
    presented = bool((authorization or "").strip() or (x_api_token or "").strip())
    if not session_ok and not presented:
        raise HTTPException(status_code=401, detail="No autenticado")
    client = BackendClient()
    headers: dict[str, str] = {"Accept": "application/json"}
    if presented:
        if authorization:
            headers["Authorization"] = authorization
        if x_api_token:
            headers["X-API-Token"] = x_api_token
    else:
        headers.update(client.headers)
    content_type = request.headers.get("content-type")
    if content_type:
        headers["Content-Type"] = content_type
    body = await request.body()
    async with __import__("httpx").AsyncClient(timeout=30.0) as http:
        upstream = await http.request(
            request.method,
            f"{client.base}/api/{path}",
            headers=headers,
            content=body if body else None,
        )
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
