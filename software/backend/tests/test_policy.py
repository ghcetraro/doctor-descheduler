from app.policy import classify, plan


def _node(name: str, cpu_used: int, pods_used: int = 2) -> dict:
    return {
        "name": name,
        "unschedulable": False,
        "labels": {},
        "taints": [],
        "cpu_alloc": 1000,
        "mem_alloc": 1000,
        "pods_alloc": 10,
        "cpu_used": cpu_used,
        "mem_used": cpu_used,
        "pods_used": pods_used,
    }


def _pod(name: str, node: str, cpu: int = 100) -> dict:
    return {
        "name": name,
        "namespace": "apps",
        "node": node,
        "phase": "Running",
        "cpu": cpu,
        "memory": cpu,
        "owner_kinds": ["ReplicaSet"],
        "replicas": 2,
        "has_pvc": False,
        "has_local_storage": False,
        "skip_affinity": False,
        "critical": False,
        "node_selector": {},
        "tolerations": [],
    }


def test_classify_bands() -> None:
    assert classify({"cpu": 10, "memory": 10, "pods": 10}) == "underutilized"
    assert classify({"cpu": 70, "memory": 10, "pods": 10}) == "overutilized"
    assert classify({"cpu": 30, "memory": 30, "pods": 30}) == "appropriately utilized"


def test_plan_evicts_from_hot_node() -> None:
    nodes = [_node("bajo", 50, pods_used=1), _node("alto", 800, pods_used=4)]
    pods = [_pod("a", "alto", 200), _pod("b", "alto", 200)]
    result = plan(nodes, pods)
    assert result["evicted"] >= 1
    assert result["evictions"][0]["namespace"] == "apps"


def test_plan_skips_single_replica() -> None:
    nodes = [_node("bajo", 50, pods_used=1), _node("alto", 800, pods_used=2)]
    pod = _pod("solo", "alto", 400)
    pod["replicas"] = 1
    result = plan(nodes, [pod])
    assert result["evicted"] == 0
