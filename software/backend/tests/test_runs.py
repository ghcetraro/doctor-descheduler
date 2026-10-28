from app.runs import BusyCluster, RunFeed, Runner, UnknownCluster


def test_unknown_cluster() -> None:
    runner = Runner(["cluster-a"])
    try:
        runner.run("cluster-b", lambda: None)
    except UnknownCluster:
        return
    raise AssertionError("debia rechazar el cluster")


def test_busy_cluster() -> None:
    runner = Runner(["cluster-a"])
    lock = runner._lock("cluster-a")
    assert lock.acquire(blocking=False)
    try:
        runner.run("cluster-a", lambda: None)
    except BusyCluster:
        return
    finally:
        lock.release()
    raise AssertionError("debia estar ocupado")


def test_run_feed_keeps_lines() -> None:
    live = RunFeed()
    assert live.snapshot("cluster-a")["lines"] == []
    live.start("cluster-a")
    live.line("cluster-a", "Consultando nodos y pods del cluster.")
    mid = live.snapshot("cluster-a")
    assert mid["running"] is True
    assert mid["lines"] == ["Consultando nodos y pods del cluster."]
    live.finish("cluster-a", True)
    done = live.snapshot("cluster-a")
    assert done["running"] is False
    assert done["ok"] is True
    assert done["lines"] == ["Consultando nodos y pods del cluster."]
