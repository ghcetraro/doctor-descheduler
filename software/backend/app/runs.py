from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class UnknownCluster(Exception):
    pass


class BusyCluster(Exception):
    pass


class RunFeed:
    """Log en memoria de la pasada en curso, para la UI."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._feeds: dict[str, dict[str, Any]] = {}

    def start(self, cluster_id: str) -> None:
        with self._guard:
            self._feeds[cluster_id] = {"running": True, "ok": None, "lines": []}

    def line(self, cluster_id: str, text: str) -> None:
        with self._guard:
            feed = self._feeds.get(cluster_id)
            if feed is None:
                feed = {"running": True, "ok": None, "lines": []}
                self._feeds[cluster_id] = feed
            lines: list[str] = feed["lines"]
            lines.append(text)
            if len(lines) > 200:
                del lines[:-200]

    def finish(self, cluster_id: str, ok: bool) -> None:
        with self._guard:
            feed = self._feeds.setdefault(cluster_id, {"lines": []})
            feed["running"] = False
            feed["ok"] = ok

    def snapshot(self, cluster_id: str) -> dict[str, Any]:
        with self._guard:
            feed = self._feeds.get(cluster_id)
            if feed is None:
                return {"running": False, "ok": None, "lines": []}
            return {
                "running": bool(feed["running"]),
                "ok": feed["ok"],
                "lines": list(feed["lines"]),
            }


feed = RunFeed()


class Runner:
    def __init__(self, clusters: list[str]) -> None:
        self.clusters = list(clusters)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, cluster_id: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(cluster_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[cluster_id] = lock
            return lock

    def run(self, cluster_id: str, action: Callable[[], None]) -> None:
        if cluster_id not in self.clusters:
            raise UnknownCluster(cluster_id)
        lock = self._lock(cluster_id)
        if not lock.acquire(blocking=False):
            raise BusyCluster(cluster_id)
        try:
            action()
        finally:
            lock.release()
