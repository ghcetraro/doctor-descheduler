from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.appearance import get_theme, set_theme
from app.config import settings
from app.db import Store
from app.engine import clients_from_argocd, run_cluster
from app.logging_config import configure_logging
from app.runs import BusyCluster, Runner, UnknownCluster, feed

configure_logging(settings.log_level)
log = logging.getLogger(__name__)


def policy_summary(policy: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    profiles = policy.get("profiles") or []
    if not profiles or not isinstance(profiles, list):
        return rows
    profile = profiles[0] if isinstance(profiles[0], dict) else {}
    exclude = ((profile.get("namespaces") or {}).get("exclude") or [])
    if exclude:
        rows.append({"label": "Namespaces excluidos", "value": ", ".join(str(item) for item in exclude)})
    for plugin in profile.get("pluginConfig") or []:
        if not isinstance(plugin, dict):
            continue
        name = str(plugin.get("name") or "")
        args = plugin.get("args") or {}
        if name == "LowNodeUtilization" and isinstance(args, dict):
            rows.append({"label": "Umbral bajo", "value": _fmt(args.get("thresholds"))})
            rows.append({"label": "Umbral destino", "value": _fmt(args.get("targetThresholds"))})
        if name == "DefaultEvictor" and isinstance(args, dict):
            rows.append(
                {
                    "label": "Evictor",
                    "value": (
                        f"minReplicas={args.get('minReplicas')} "
                        f"ignorePvcPods={args.get('ignorePvcPods')} "
                        f"nodeFit={args.get('nodeFit')}"
                    ),
                }
            )
    return rows


def _fmt(value: Any) -> str:
    if not isinstance(value, dict):
        return "—"
    return " ".join(f"{key}={item}%" for key, item in value.items())


runner = Runner(settings.clusters)


def execute_cluster(store: Store, cluster_id: str) -> None:
    def say(text: str) -> None:
        feed.line(cluster_id, text)

    feed.start(cluster_id)
    api = None
    ok = False
    try:
        say("Leyendo el kubeconfig de ArgoCD.")
        clients = clients_from_argocd([cluster_id], settings.argocd_namespace)
        api = clients.get(cluster_id)
        if api is None:
            say("No hay kubeconfig en el secret de ArgoCD.")
            store.save_error(cluster_id, "sin kubeconfig en el secret de ArgoCD")
            return
        snapshot = run_cluster(api, cluster_id, settings.dry_run, on_line=say)
        store.save_snapshot(snapshot)
        ok = True
    except Exception as exc:  # noqa: BLE001
        log.warning("cluster %s: %s", cluster_id, exc)
        say(f"Error: {exc}")
        store.save_error(cluster_id, str(exc))
    finally:
        feed.finish(cluster_id, ok)
        if api is not None:
            try:
                api.close()
            except Exception:  # noqa: BLE001
                pass


def run_cluster_id(store: Store, cluster_id: str) -> None:
    runner.run(cluster_id, lambda: execute_cluster(store, cluster_id))


def run_once(store: Store) -> None:
    for cluster_id in settings.clusters:
        try:
            run_cluster_id(store, cluster_id)
        except BusyCluster:
            log.info("cluster %s ocupado por una pasada manual", cluster_id)


async def loop(store: Store) -> None:
    while True:
        await asyncio.to_thread(run_once, store)
        await asyncio.sleep(max(60, settings.interval_seconds))


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = Store(Path(settings.data_dir) / "descheduler.db")
    store.ensure_api_tokens(settings.api_token)
    app.state.store = store
    task = asyncio.create_task(loop(store))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="doctor-descheduler-api", version=settings.app_version, lifespan=lifespan)


def _presented(authorization: Optional[str], x_api_token: Optional[str]) -> str:
    raw = ""
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
    return raw or (x_api_token or "").strip()


def _auth(authorization: Optional[str], x_api_token: Optional[str]) -> None:
    if not settings.api_token.strip():
        raise HTTPException(status_code=503, detail="API_TOKEN vacio")
    store: Store = app.state.store
    if not store.api_token_matches(_presented(authorization, x_api_token), settings.api_token):
        raise HTTPException(status_code=401, detail="No autenticado")


def _avg_usage(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[float]] = {"cpu": [], "memory": [], "pods": []}
    for node in nodes:
        pct = node.get("usage_percentage") or {}
        if not isinstance(pct, dict):
            continue
        for key in buckets:
            value = pct.get(key)
            if isinstance(value, (int, float)):
                buckets[key].append(float(value))
    averages: dict[str, Any] = {}
    for key, values in buckets.items():
        averages[key] = round(sum(values) / len(values)) if values else None
    present = [averages[key] for key in ("cpu", "memory", "pods") if averages[key] is not None]
    averages["usage"] = round(sum(present) / len(present)) if present else None
    return averages


def _fleet_row(row: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if row.get("snapshot_json"):
        snapshot = json.loads(row["snapshot_json"])
    jobs = snapshot.get("jobs") or []
    last = jobs[0] if jobs else {}
    usage = _avg_usage(last.get("nodes") or [])
    return {
        "id": row["cluster"],
        "ok": bool(row["ok"]),
        "error": row.get("error") or "",
        "checked_at": row.get("checked_at"),
        "dry_run": snapshot.get("dry_run"),
        "schedule": (snapshot.get("cronjob") or {}).get("schedule"),
        "last_start": last.get("start_time"),
        "overutilized": last.get("overutilized"),
        "underutilized": last.get("underutilized"),
        "evicted": last.get("evicted"),
        "usage": usage["usage"],
        "cpu": usage["cpu"],
        "memory": usage["memory"],
        "pods": usage["pods"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class TokenCreate(BaseModel):
    name: str


class AppearanceBody(BaseModel):
    theme: str


@app.get("/api/v1/appearance")
def read_appearance(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, str]:
    _auth(authorization, x_api_token)
    return {"theme": get_theme()}


@app.post("/api/v1/appearance")
def write_appearance(
    body: AppearanceBody,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, str]:
    _auth(authorization, x_api_token)
    try:
        theme = set_theme(body.theme)
    except Exception as exc:  # noqa: BLE001
        log.warning("no se guardo la apariencia: %s", exc)
        raise HTTPException(status_code=503, detail="No se pudo guardar la apariencia") from exc
    return {"theme": theme}


@app.get("/api/tokens")
def list_tokens(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    return {"tokens": store.list_api_tokens(settings.api_token)}


@app.post("/api/tokens")
def create_token(
    body: TokenCreate,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, str]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    try:
        raw = store.create_api_token(body.name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="No se pudo crear el token") from exc
    return {"name": body.name.strip(), "token": raw}


@app.delete("/api/tokens/{token_id}")
def delete_token(
    token_id: int,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, bool]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    store.revoke_api_token(token_id)
    return {"ok": True}


@app.get("/api/v1/fleet")
def fleet(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    known = {row["cluster"]: row for row in store.status_rows()}
    clusters = []
    for cluster_id in settings.clusters:
        if cluster_id in known:
            clusters.append(_fleet_row(known[cluster_id]))
        else:
            clusters.append({"id": cluster_id, "ok": False, "error": "sin lectura", "dry_run": None})
    return {"clusters": clusters}


@app.post("/api/v1/clusters/{cluster_id}/run")
def run_cluster_now(
    cluster_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    try:
        run_cluster_id(store, cluster_id)
    except UnknownCluster as exc:
        raise HTTPException(status_code=404, detail="cluster desconocido") from exc
    except BusyCluster as exc:
        raise HTTPException(status_code=409, detail="ya hay una pasada en curso") from exc
    return {"ok": True, "id": cluster_id}


@app.get("/api/v1/clusters/{cluster_id}/progress")
def run_progress(
    cluster_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    if cluster_id not in settings.clusters:
        raise HTTPException(status_code=404, detail="cluster desconocido")
    return {"id": cluster_id, **feed.snapshot(cluster_id)}


@app.get("/api/v1/clusters/{cluster_id}")
def cluster_detail(
    cluster_id: str,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    snapshot = store.snapshot_for(cluster_id) or {}
    return {
        "id": cluster_id,
        "snapshot": snapshot,
        "policy_summary": policy_summary(snapshot.get("policy") or {}),
        "policy_history": store.policy_history(cluster_id),
    }


@app.get("/api/v1/history")
def history(
    cluster: str = "",
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    return {"runs": store.runs(cluster)}


@app.get("/api/export")
def export_backup(
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    return store.export()


class ImportBody(BaseModel):
    version: int = 1
    runs: list[dict[str, Any]] = []
    policies: list[dict[str, Any]] = []
    status: list[dict[str, Any]] = []


@app.post("/api/import")
def import_backup(
    body: ImportBody,
    authorization: Optional[str] = Header(default=None),
    x_api_token: Optional[str] = Header(default=None),
) -> dict[str, str]:
    _auth(authorization, x_api_token)
    store: Store = app.state.store
    store.import_payload(body.model_dump())
    return {"status": "ok"}
