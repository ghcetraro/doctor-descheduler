"""LowNodeUtilization + filtros del evictor, sobre dicts ya normalizados.

El uso es requests / allocatable (CPU, memoria y cantidad de pods), igual que
el chart descheduler cuando no hay metrics provider.
"""

from __future__ import annotations

from typing import Any

THRESHOLDS = {"cpu": 15, "memory": 15, "pods": 15}
TARGET_THRESHOLDS = {"cpu": 60, "memory": 60, "pods": 60}
EXCLUDED_NAMESPACES = frozenset(
    {
        "kube-system",
        "kube-public",
        "kube-node-lease",
        "descheduler",
        "argocd",
        "cert-manager",
    }
)
MIN_REPLICAS = 2

POLICY = {
    "profiles": [
        {
            "name": "default",
            "namespaces": {"exclude": sorted(EXCLUDED_NAMESPACES)},
            "pluginConfig": [
                {
                    "name": "DefaultEvictor",
                    "args": {
                        "ignorePvcPods": True,
                        "evictLocalStoragePods": False,
                        "nodeFit": True,
                        "minReplicas": MIN_REPLICAS,
                    },
                },
                {
                    "name": "LowNodeUtilization",
                    "args": {
                        "thresholds": dict(THRESHOLDS),
                        "targetThresholds": dict(TARGET_THRESHOLDS),
                    },
                },
            ],
        }
    ]
}


def percent(used: int, capacity: int) -> int:
    if capacity <= 0:
        return 0
    return int(round(100 * used / capacity))


def classify(usage: dict[str, int]) -> str:
    over = any(int(usage.get(key) or 0) > TARGET_THRESHOLDS[key] for key in TARGET_THRESHOLDS)
    if over:
        return "overutilized"
    under = all(int(usage.get(key) or 0) < THRESHOLDS[key] for key in THRESHOLDS)
    if under:
        return "underutilized"
    return "appropriately utilized"


def refresh(node: dict[str, Any]) -> None:
    usage = {
        "cpu": percent(int(node["cpu_used"]), int(node["cpu_alloc"])),
        "memory": percent(int(node["mem_used"]), int(node["mem_alloc"])),
        "pods": percent(int(node["pods_used"]), int(node["pods_alloc"])),
    }
    node["usage_percentage"] = usage
    node["category"] = classify(usage)


def _tolerates(pod: dict[str, Any], node: dict[str, Any]) -> bool:
    for taint in node.get("taints") or []:
        effect = str(taint.get("effect") or "")
        if effect == "PreferNoSchedule":
            continue
        matched = False
        for tol in pod.get("tolerations") or []:
            key = tol.get("key")
            if key not in (None, "") and key != taint.get("key"):
                continue
            operator = tol.get("operator") or "Equal"
            if operator == "Equal" and (tol.get("value") or "") != (taint.get("value") or ""):
                continue
            if operator not in ("Equal", "Exists"):
                continue
            tol_effect = tol.get("effect")
            if tol_effect not in (None, "") and tol_effect != effect:
                continue
            matched = True
            break
        if not matched:
            return False
    return True


def _selector_ok(pod: dict[str, Any], node: dict[str, Any]) -> bool:
    labels = node.get("labels") or {}
    for key, value in (pod.get("node_selector") or {}).items():
        if labels.get(key) != value:
            return False
    return True


def _fits_resources(pod: dict[str, Any], node: dict[str, Any]) -> bool:
    if int(node["cpu_alloc"]) - int(node["cpu_used"]) < int(pod.get("cpu") or 0):
        return False
    if int(node["mem_alloc"]) - int(node["mem_used"]) < int(pod.get("memory") or 0):
        return False
    if int(node["pods_alloc"]) - int(node["pods_used"]) < 1:
        return False
    return True


def fits(pod: dict[str, Any], node: dict[str, Any]) -> bool:
    if node.get("unschedulable"):
        return False
    if not _tolerates(pod, node):
        return False
    if not _selector_ok(pod, node):
        return False
    return _fits_resources(pod, node)


def skip_reason(pod: dict[str, Any]) -> str:
    if pod.get("phase") != "Running":
        return "no está Running"
    if pod.get("namespace") in EXCLUDED_NAMESPACES:
        return "namespace excluido"
    if pod.get("critical"):
        return "prioridad crítica"
    kinds = set(pod.get("owner_kinds") or [])
    if "DaemonSet" in kinds:
        return "DaemonSet"
    if not kinds:
        return "sin controlador"
    if "Job" in kinds:
        return "Job"
    replicas = pod.get("replicas")
    if not isinstance(replicas, int) or replicas < MIN_REPLICAS:
        return f"replicas<{MIN_REPLICAS}"
    if pod.get("has_pvc"):
        return "tiene PVC"
    if pod.get("has_local_storage"):
        return "almacenamiento local"
    if pod.get("skip_affinity"):
        return "afinidad que esta app no evalúa"
    return ""


def plan(nodes: list[dict[str, Any]], pods: list[dict[str, Any]]) -> dict[str, Any]:
    for node in nodes:
        refresh(node)
    under = [node for node in nodes if node["category"] == "underutilized"]
    over = [node for node in nodes if node["category"] == "overutilized"]
    notes: list[str] = []
    evictions: list[dict[str, str]] = []
    if not under or not over:
        notes.append("Nada que balancear: falta un nodo bajo y uno alto a la vez.")
        return _result(nodes, under, over, evictions, notes)

    pods_by_node: dict[str, list[dict[str, Any]]] = {}
    for pod in pods:
        pods_by_node.setdefault(str(pod.get("node") or ""), []).append(pod)

    for node in over:
        candidates = sorted(
            pods_by_node.get(node["name"], []),
            key=lambda item: (int(item.get("cpu") or 0), int(item.get("memory") or 0)),
        )
        for pod in candidates:
            if node["category"] != "overutilized":
                break
            reason = skip_reason(pod)
            if reason:
                continue
            targets = [other for other in under if other["name"] != node["name"] and fits(pod, other)]
            if not targets:
                continue
            ref = f"{pod['namespace']}/{pod['name']}"
            evictions.append(
                {
                    "pod": ref,
                    "namespace": str(pod["namespace"]),
                    "name": str(pod["name"]),
                    "line": f"evict pod={ref} desde {node['name']} hacia nodo bajo",
                }
            )
            node["cpu_used"] = max(0, int(node["cpu_used"]) - int(pod.get("cpu") or 0))
            node["mem_used"] = max(0, int(node["mem_used"]) - int(pod.get("memory") or 0))
            node["pods_used"] = max(0, int(node["pods_used"]) - 1)
            refresh(node)
    if not evictions and not notes:
        notes.append("Hay nodos altos y bajos, pero ningún pod pasó los filtros.")
    return _result(nodes, under, over, evictions, notes)


def _result(
    nodes: list[dict[str, Any]],
    under: list[dict[str, Any]],
    over: list[dict[str, Any]],
    evictions: list[dict[str, str]],
    notes: list[str],
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "name": node["name"],
                "category": node["category"],
                "usage_percentage": dict(node["usage_percentage"]),
            }
            for node in nodes
        ],
        "underutilized": len(under),
        "overutilized": len(over),
        "evictions": evictions,
        "notes": notes,
        "evicted": len(evictions),
    }
