from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

NAME = "doctor-descheduler-appearance"
_cached: str | None = None


def normalize_theme(value: object) -> str:
    return "light" if str(value or "").strip().lower() == "light" else "dark"


def pod_namespace() -> str:
    path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    if path.is_file():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    return "doctor-descheduler"


def get_theme() -> str:
    global _cached
    if _cached in {"light", "dark"}:
        return _cached
    try:
        from kubernetes import client, config

        config.load_incluster_config()
        found = client.CoreV1Api().read_namespaced_config_map(NAME, pod_namespace())
        _cached = normalize_theme((found.data or {}).get("theme"))
    except Exception as exc:  # noqa: BLE001
        status = getattr(exc, "status", None)
        if status == 404:
            _cached = "dark"
            return _cached
        log.warning("apariencia: %s", exc)
        return "dark"
    return _cached or "dark"


def set_theme(theme: str) -> str:
    global _cached
    value = normalize_theme(theme)
    from kubernetes import client, config
    from kubernetes.client import ApiException

    config.load_incluster_config()
    core = client.CoreV1Api()
    namespace = pod_namespace()
    try:
        core.patch_namespaced_config_map(NAME, namespace, {"data": {"theme": value}})
    except ApiException as exc:
        if exc.status != 404:
            raise
        core.create_namespaced_config_map(
            namespace,
            client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=NAME, labels={"app": "doctor-descheduler"}),
                data={"theme": value},
            ),
        )
    _cached = value
    return value
