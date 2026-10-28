from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.backend_client import BackendClient
from app.web_context import require_web_auth, web_context

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _render(request: Request, name: str, page: str, extra: dict[str, Any]) -> HTMLResponse:
    if redirect := require_web_auth(request):
        return redirect
    return templates.TemplateResponse(
        request,
        name,
        {"page": page, **web_context(request), **extra},
    )


async def _fleet() -> tuple[list[dict[str, Any]], str]:
    try:
        payload = await BackendClient().get_json("/api/v1/fleet")
        return list(payload.get("clusters") or []), ""
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request) -> Any:
    clusters, error = await _fleet()
    return _render(request, "dashboard.html", "dashboard", {"clusters": clusters, "load_error": error})


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def fleet_page(request: Request) -> Any:
    clusters, error = await _fleet()
    flash = request.session.pop("fleet_flash", None) if hasattr(request, "session") else None
    return _render(
        request,
        "index.html",
        "fleet",
        {"clusters": clusters, "load_error": error, "flash": flash if isinstance(flash, dict) else None},
    )


@router.post("/cluster/{cluster_id}/ejecutar", include_in_schema=False)
async def run_cluster_page(request: Request, cluster_id: str) -> Any:
    if redirect := require_web_auth(request):
        return redirect
    import httpx

    message = f"Pasada de {cluster_id} terminada."
    level = "success"
    try:
        await BackendClient().post_json(f"/api/v1/clusters/{cluster_id}/run", {}, timeout=180)
    except httpx.HTTPStatusError as exc:
        level = "error"
        if exc.response.status_code == 409:
            message = f"Ya hay una pasada de {cluster_id} en curso."
        elif exc.response.status_code == 404:
            message = f"{cluster_id} no está en la lista de clusters."
        else:
            message = f"No se pudo ejecutar {cluster_id}."
    except Exception:  # noqa: BLE001
        level = "error"
        message = f"No se pudo ejecutar {cluster_id}."
    request.session["fleet_flash"] = {"message": message, "level": level}
    return RedirectResponse("/", status_code=303)


@router.get("/cluster/{cluster_id}", response_class=HTMLResponse, include_in_schema=False)
async def cluster_page(request: Request, cluster_id: str) -> Any:
    error = ""
    detail: dict[str, Any] = {}
    try:
        detail = await BackendClient().get_json(f"/api/v1/clusters/{cluster_id}")
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    return _render(
        request,
        "cluster.html",
        "dashboard",
        {"cluster_id": cluster_id, "detail": detail, "load_error": error},
    )


@router.get("/historial", response_class=HTMLResponse, include_in_schema=False)
async def history_page(request: Request) -> Any:
    error = ""
    runs: list[dict[str, Any]] = []
    try:
        payload = await BackendClient().get_json("/api/v1/history")
        runs = list(payload.get("runs") or [])
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
    return _render(request, "history.html", "history", {"runs": runs, "load_error": error})


@router.get("/config", response_class=HTMLResponse, include_in_schema=False)
async def config_page(request: Request) -> Any:
    if redirect := require_web_auth(request):
        return redirect
    users = request.app.state.users
    tokens: list[dict[str, Any]] = []
    try:
        payload = await BackendClient().get_json("/api/tokens")
        tokens = list(payload.get("tokens") or [])
    except Exception:  # noqa: BLE001
        tokens = []
    flash = request.session.pop("api_token_flash", None) if hasattr(request, "session") else None
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "page": "config",
            "active_tab": request.query_params.get("tab") or "apariencia",
            "app_users": users.list_users(),
            "api_tokens": tokens,
            "new_api_token": (flash or {}).get("token") if isinstance(flash, dict) else None,
            "new_api_token_name": (flash or {}).get("name") if isinstance(flash, dict) else None,
            "token_ok": request.query_params.get("token_ok") == "1",
            "token_revoked": request.query_params.get("token_revoked") == "1",
            **web_context(request),
        },
    )


def _admin_or_redirect(request: Request) -> Any:
    if redirect := require_web_auth(request):
        return redirect
    from app.auth import AuthService

    auth: AuthService = request.app.state.auth
    if not auth.is_admin(request):
        return RedirectResponse("/config?tab=api", status_code=303)
    return None


@router.post("/config/api/crear", include_in_schema=False)
async def create_api_token(request: Request, name: str = Form(...)) -> Any:
    if blocked := _admin_or_redirect(request):
        return blocked
    try:
        data = await BackendClient().post_json("/api/tokens", {"name": name})
        request.session["api_token_flash"] = {"token": data.get("token"), "name": data.get("name")}
    except Exception:  # noqa: BLE001
        return RedirectResponse("/config?tab=api", status_code=303)
    return RedirectResponse("/config?tab=api&token_ok=1", status_code=303)


@router.get("/config/api/eliminar/{token_id}", include_in_schema=False)
async def revoke_api_token(request: Request, token_id: int) -> Any:
    if blocked := _admin_or_redirect(request):
        return blocked
    try:
        await BackendClient().delete(f"/api/tokens/{token_id}")
    except Exception:  # noqa: BLE001
        return RedirectResponse("/config?tab=api", status_code=303)
    return RedirectResponse("/config?tab=api&token_revoked=1", status_code=303)


@router.get("/config/exportar", include_in_schema=False)
async def export_backup(request: Request) -> Any:
    if redirect := require_web_auth(request):
        return redirect
    from fastapi.responses import Response

    client = BackendClient()
    async with __import__("httpx").AsyncClient(timeout=30.0) as http:
        response = await http.get(f"{client.base}/api/export", headers=client.headers)
        response.raise_for_status()
    return Response(
        content=response.content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=doctor-descheduler.json"},
    )
