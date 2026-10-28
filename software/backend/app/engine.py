from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException, Configuration, V1Eviction, V1ObjectMeta

from app.policy import POLICY, plan

log = logging.getLogger(__name__)


def parse_cpu(value: Any) -> int:
    raw = str(value or "0").strip()
    if raw.endswith("m"):
        return int(float(raw[:-1]))
    return int(float(raw) * 1000)


def parse_mem(value: Any) -> int:
    raw = str(value or "0").strip()
    units = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
    }
    for suffix, factor in units.items():
        if raw.endswith(suffix):
            return int(float(raw[: -len(suffix)]) * factor)
    return int(float(raw or 0))


def _decode(data: dict[str, str], key: str) -> str:
    raw = data.get(key) or ""
    if not raw:
        return ""
    return base64.b64decode(raw).decode()


def clients_from_argocd(cluster_ids: list[str], namespace: str) -> dict[str, client.ApiClient]:
    config.load_incluster_config()
    core = client.CoreV1Api()
    found: dict[str, client.ApiClient] = {}
    for cluster_id in cluster_ids:
        try:
            secret = core.read_namespaced_secret(cluster_id, namespace)
        except ApiException as exc:
            log.warning("secret %s/%s: %s", namespace, cluster_id, exc.reason)
            continue
        data = secret.data or {}
        server = _decode(data, "server").strip()
        blob = _decode(data, "config")
        try:
            parsed = json.loads(blob) if blob else {}
        except json.JSONDecodeError:
            parsed = {}
        tls = parsed.get("tlsClientConfig") or {}
        user: dict[str, Any] = {}
        if tls.get("certData") and tls.get("keyData"):
            user["client-certificate-data"] = tls["certData"]
            user["client-key-data"] = tls["keyData"]
        elif parsed.get("bearerToken"):
            user["token"] = parsed["bearerToken"]
        cluster_spec: dict[str, Any] = {"server": server}
        if tls.get("caData"):
            cluster_spec["certificate-authority-data"] = tls["caData"]
        if tls.get("insecure"):
            cluster_spec["insecure-skip-tls-verify"] = True
        kubeconfig = {
            "apiVersion": "v1",
            "kind": "Config",
            "current-context": cluster_id,
            "clusters": [{"name": cluster_id, "cluster": cluster_spec}],
            "users": [{"name": cluster_id, "user": user}],
            "contexts": [{"name": cluster_id, "context": {"cluster": cluster_id, "user": cluster_id}}],
        }
        configuration = Configuration()
        config.load_kube_config_from_dict(kubeconfig, client_configuration=configuration)
        found[cluster_id] = client.ApiClient(configuration)
    return found


def _requests(pod: Any) -> tuple[int, int]:
    cpu = memory = 0
    for container in pod.spec.containers or []:
        requests = {}
        if container.resources and container.resources.requests:
            requests = container.resources.requests
        cpu += parse_cpu(requests.get("cpu"))
        memory += parse_mem(requests.get("memory"))
    return cpu, memory


def _owner_replicas(apps_api: Any, namespace: str, owners: list[Any], cache: dict[tuple[str, str, str], int]) -> tuple[list[str], int | None]:
    kinds = [str(owner.kind) for owner in owners if owner.controller]
    replicas = None
    for owner in owners:
        if not owner.controller:
            continue
        key = (namespace, str(owner.kind), str(owner.name))
        if key in cache:
            replicas = cache[key]
            continue
        if owner.kind == "ReplicaSet":
            item = apps_api.read_namespaced_replica_set(owner.name, namespace)
            replicas = int(item.spec.replicas or 0)
        elif owner.kind == "StatefulSet":
            item = apps_api.read_namespaced_stateful_set(owner.name, namespace)
            replicas = int(item.spec.replicas or 0)
        elif owner.kind == "ReplicationController":
            core = client.CoreV1Api(apps_api.api_client)
            item = core.read_namespaced_replication_controller(owner.name, namespace)
            replicas = int(item.spec.replicas or 0)
        else:
            continue
        cache[key] = replicas
    return kinds, replicas


def _pod_dict(pod: Any, apps_api: Any, cache: dict[tuple[str, str, str], int]) -> dict[str, Any]:
    spec = pod.spec
    volumes = spec.volumes or []
    has_pvc = any(volume.persistent_volume_claim for volume in volumes)
    has_local = any(volume.host_path or volume.empty_dir for volume in volumes)
    affinity = spec.affinity
    skip_affinity = False
    if affinity and (affinity.pod_affinity or affinity.pod_anti_affinity):
        required = False
        if affinity.pod_affinity and affinity.pod_affinity.required_during_scheduling_ignored_during_execution:
            required = True
        if affinity.pod_anti_affinity and affinity.pod_anti_affinity.required_during_scheduling_ignored_during_execution:
            required = True
        skip_affinity = required
    owners = list(pod.metadata.owner_references or [])
    kinds, replicas = _owner_replicas(apps_api, pod.metadata.namespace, owners, cache)
    priority = str(spec.priority_class_name or "")
    cpu, memory = _requests(pod)
    tolerations = []
    for item in spec.tolerations or []:
        tolerations.append({"key": item.key, "value": item.value, "operator": item.operator, "effect": item.effect})
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "node": spec.node_name or "",
        "phase": pod.status.phase or "",
        "cpu": cpu,
        "memory": memory,
        "owner_kinds": kinds,
        "replicas": replicas,
        "has_pvc": has_pvc,
        "has_local_storage": has_local,
        "skip_affinity": skip_affinity,
        "critical": priority in {"system-cluster-critical", "system-node-critical"},
        "node_selector": dict(spec.node_selector or {}),
        "tolerations": tolerations,
    }


def _node_dict(node: Any, pods: list[dict[str, Any]]) -> dict[str, Any]:
    alloc = node.status.allocatable or {}
    name = node.metadata.name
    mine = [pod for pod in pods if pod["node"] == name and pod["phase"] not in {"Succeeded", "Failed"}]
    taints = []
    for taint in node.spec.taints or []:
        taints.append({"key": taint.key, "value": taint.value, "effect": taint.effect})
    return {
        "name": name,
        "unschedulable": bool(node.spec.unschedulable),
        "labels": dict(node.metadata.labels or {}),
        "taints": taints,
        "cpu_alloc": parse_cpu(alloc.get("cpu")),
        "mem_alloc": parse_mem(alloc.get("memory")),
        "pods_alloc": int(alloc.get("pods") or 0),
        "cpu_used": sum(int(pod["cpu"]) for pod in mine),
        "mem_used": sum(int(pod["memory"]) for pod in mine),
        "pods_used": len(mine),
    }


def run_cluster(
    api: client.ApiClient,
    cluster_id: str,
    dry_run: bool,
    on_line: Any = None,
) -> dict[str, Any]:
    def say(text: str) -> None:
        log.info("%s: %s", cluster_id, text)
        if on_line is not None:
            on_line(text)

    core = client.CoreV1Api(api)
    apps_api = client.AppsV1Api(api)
    say("Modo dry-run: no mueve pods." if dry_run else "Modo real: puede evictar pods.")
    say("Consultando nodos y pods del cluster.")
    node_list = core.list_node()
    pod_list = core.list_pod_for_all_namespaces()
    cache: dict[tuple[str, str, str], int] = {}
    pod_dicts = []
    for pod in pod_list.items:
        if pod.metadata.deletion_timestamp:
            continue
        if (pod.status.phase or "") in {"Succeeded", "Failed"}:
            continue
        try:
            pod_dicts.append(_pod_dict(pod, apps_api, cache))
        except ApiException as exc:
            log.info("owner %s/%s: %s", pod.metadata.namespace, pod.metadata.name, exc.reason)
    nodes = [_node_dict(node, pod_dicts) for node in node_list.items]
    say(f"{len(nodes)} nodos, {len(pod_dicts)} pods.")
    decided = plan(nodes, pod_dicts)
    high = [item["name"] for item in decided["nodes"] if item["category"] == "overutilized"]
    low = [item["name"] for item in decided["nodes"] if item["category"] == "underutilized"]
    say(f"Nodos altos: {', '.join(high) or 'ninguno'}. Bajos: {', '.join(low) or 'ninguno'}.")
    for note in decided["notes"]:
        say(note)
    applied: list[dict[str, str]] = []
    for item in decided["evictions"]:
        line = item["line"]
        if dry_run:
            say("dry-run " + line)
            applied.append({"pod": item["pod"], "line": "dry-run " + line})
            continue
        say(line)
        body = V1Eviction(metadata=V1ObjectMeta(name=item["name"], namespace=item["namespace"]))
        try:
            core.create_namespaced_pod_eviction(item["name"], item["namespace"], body)
            applied.append({"pod": item["pod"], "line": line})
            say(f"Evictado {item['pod']}.")
        except ApiException as exc:
            failed = f"no se evictó {item['pod']}: {exc.status} {exc.reason}"
            applied.append({"pod": item["pod"], "line": failed})
            say(failed)
    now = datetime.now(timezone.utc).isoformat()
    evicted = len([item for item in applied if not item["line"].startswith("no se evictó")])
    shown = len(applied) if dry_run else evicted
    say(f"Terminó. Evictions: {shown}.")
    return {
        "cluster": cluster_id,
        "dry_run": dry_run,
        "policy": POLICY,
        "policy_configmap": "embebida",
        "cronjob": {
            "name": "doctor-descheduler",
            "schedule": "*/15 * * * *",
            "time_zone": "America/Argentina/Buenos_Aires",
        },
        "jobs": [
            {
                "name": now,
                "start_time": now,
                "succeeded": True,
                "underutilized": decided["underutilized"],
                "overutilized": decided["overutilized"],
                "evicted": evicted if not dry_run else len(applied),
                "nodes": decided["nodes"],
                "notes": decided["notes"],
                "evictions": applied,
                "excerpt": [item["line"] for item in applied] or list(decided["notes"]),
            }
        ],
    }
