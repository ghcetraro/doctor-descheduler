from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_log(payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload) if payload else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    notes = [str(line) for line in data.get("notes") or [] if str(line).strip()]
    excerpt = [str(line) for line in data.get("excerpt") or [] if str(line).strip()]
    evictions = data.get("evictions") or []
    moved = [str(item.get("pod") or "") for item in evictions if isinstance(item, dict) and item.get("pod")]
    evicted = int(data.get("evicted") or 0)
    error = str(data.get("log_error") or "")
    if error and not notes and not excerpt:
        summary = "No se pudo leer el log de este Job."
    elif moved or evicted:
        summary = f"Movió {evicted or len(moved)} pod(s)."
    else:
        summary = "No movió pods."
    lines = excerpt or notes
    for item in evictions:
        if isinstance(item, dict) and item.get("line"):
            text = str(item["line"])
            if text not in lines:
                lines.append(text)
    return {"summary": summary, "lines": lines[:40], "moved_pods": moved}


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
              id INTEGER PRIMARY KEY,
              cluster TEXT NOT NULL,
              job_name TEXT NOT NULL,
              start_time TEXT,
              succeeded INTEGER,
              underutilized INTEGER,
              overutilized INTEGER,
              evicted INTEGER,
              payload TEXT NOT NULL,
              UNIQUE(cluster, job_name)
            );
            CREATE TABLE IF NOT EXISTS policies (
              id INTEGER PRIMARY KEY,
              cluster TEXT NOT NULL,
              fingerprint TEXT NOT NULL,
              policy_json TEXT NOT NULL,
              seen_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cluster_status (
              cluster TEXT PRIMARY KEY,
              ok INTEGER NOT NULL,
              error TEXT,
              checked_at TEXT,
              snapshot_json TEXT
            );
            """
        )
        self._conn.commit()

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        cluster = str(snapshot.get("cluster") or "")
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cluster_status (cluster, ok, error, checked_at, snapshot_json)
                VALUES (?, 1, '', ?, ?)
                ON CONFLICT(cluster) DO UPDATE SET
                  ok = 1, error = '', checked_at = excluded.checked_at, snapshot_json = excluded.snapshot_json
                """,
                (cluster, _now(), json.dumps(snapshot)),
            )
            for job in snapshot.get("jobs") or []:
                name = str(job.get("name") or "")
                if not name:
                    continue
                self._conn.execute(
                    """
                    INSERT INTO runs (cluster, job_name, start_time, succeeded, underutilized, overutilized, evicted, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cluster, job_name) DO UPDATE SET
                      start_time = excluded.start_time,
                      succeeded = excluded.succeeded,
                      underutilized = excluded.underutilized,
                      overutilized = excluded.overutilized,
                      evicted = excluded.evicted,
                      payload = excluded.payload
                    """,
                    (
                        cluster,
                        name,
                        job.get("start_time"),
                        1 if job.get("succeeded") else 0,
                        int(job.get("underutilized") or 0),
                        int(job.get("overutilized") or 0),
                        int(job.get("evicted") or 0),
                        json.dumps(job),
                    ),
                )
            policy = snapshot.get("policy") or {}
            raw = json.dumps(policy, sort_keys=True)
            fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:12]
            last = self._conn.execute(
                "SELECT fingerprint FROM policies WHERE cluster = ? ORDER BY id DESC LIMIT 1",
                (cluster,),
            ).fetchone()
            if last is None or last["fingerprint"] != fingerprint:
                self._conn.execute(
                    "INSERT INTO policies (cluster, fingerprint, policy_json, seen_at) VALUES (?, ?, ?, ?)",
                    (cluster, fingerprint, raw, _now()),
                )
            self._conn.commit()

    def save_error(self, cluster: str, error: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cluster_status (cluster, ok, error, checked_at, snapshot_json)
                VALUES (?, 0, ?, ?, NULL)
                ON CONFLICT(cluster) DO UPDATE SET
                  ok = 0, error = excluded.error, checked_at = excluded.checked_at
                """,
                (cluster, error[:500], _now()),
            )
            self._conn.commit()

    def status_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT cluster, ok, error, checked_at, snapshot_json FROM cluster_status ORDER BY cluster"
            ).fetchall()
        return [dict(row) for row in rows]

    def snapshot_for(self, cluster: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT snapshot_json FROM cluster_status WHERE cluster = ?",
                (cluster,),
            ).fetchone()
        if row is None or not row["snapshot_json"]:
            return None
        return json.loads(row["snapshot_json"])

    def policy_history(self, cluster: str) -> list[dict[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT fingerprint, seen_at FROM policies WHERE cluster = ? ORDER BY id DESC LIMIT 20",
                (cluster,),
            ).fetchall()
        return [dict(row) for row in rows]

    def runs(self, cluster: str = "") -> list[dict[str, Any]]:
        query = "SELECT cluster, job_name, start_time, succeeded, underutilized, overutilized, evicted, payload FROM runs"
        args: tuple = ()
        if cluster:
            query += " WHERE cluster = ?"
            args = (cluster,)
        query += " ORDER BY start_time DESC LIMIT 200"
        with self._lock:
            rows = self._conn.execute(query, args).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item.update(_run_log(item.pop("payload", "")))
            out.append(item)
        return out

    def export(self) -> dict[str, Any]:
        with self._lock:
            runs = [dict(row) for row in self._conn.execute("SELECT * FROM runs").fetchall()]
            policies = [dict(row) for row in self._conn.execute("SELECT * FROM policies").fetchall()]
            status = [dict(row) for row in self._conn.execute("SELECT * FROM cluster_status").fetchall()]
        return {"version": 1, "runs": runs, "policies": policies, "status": status}

    def import_payload(self, payload: dict[str, Any]) -> None:
        with self._lock:
            for row in payload.get("runs") or []:
                self._conn.execute(
                    """
                    INSERT INTO runs (cluster, job_name, start_time, succeeded, underutilized, overutilized, evicted, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cluster, job_name) DO UPDATE SET payload = excluded.payload
                    """,
                    (
                        row.get("cluster"),
                        row.get("job_name"),
                        row.get("start_time"),
                        row.get("succeeded") or 0,
                        row.get("underutilized") or 0,
                        row.get("overutilized") or 0,
                        row.get("evicted") or 0,
                        row.get("payload") or "{}",
                    ),
                )
            for row in payload.get("policies") or []:
                self._conn.execute(
                    "INSERT INTO policies (cluster, fingerprint, policy_json, seen_at) VALUES (?, ?, ?, ?)",
                    (row.get("cluster"), row.get("fingerprint"), row.get("policy_json"), row.get("seen_at")),
                )
            self._conn.commit()

    def ensure_api_tokens(self, api_token: str) -> None:
        raw = (api_token or "").strip()
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_tokens (
                  id INTEGER PRIMARY KEY,
                  name TEXT NOT NULL UNIQUE,
                  token_hash TEXT NOT NULL,
                  token_prefix TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            if raw:
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                row = self._conn.execute("SELECT id FROM api_tokens WHERE name = 'helm'").fetchone()
                if row:
                    self._conn.execute(
                        "UPDATE api_tokens SET token_hash = ?, token_prefix = ? WHERE name = 'helm'",
                        (digest, raw[:8]),
                    )
                else:
                    self._conn.execute(
                        "INSERT INTO api_tokens (name, token_hash, token_prefix, created_at) VALUES ('helm', ?, ?, ?)",
                        (digest, raw[:8], _now()),
                    )
            self._conn.commit()

    def list_api_tokens(self, helm_value: str = "") -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, token_prefix, created_at FROM api_tokens ORDER BY id"
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["token_value"] = helm_value if item["name"] == "helm" else ""
            out.append(item)
        return out

    def create_api_token(self, name: str) -> str:
        import secrets

        label = name.strip()
        if not label or label == "helm":
            raise ValueError("Nombre invalido")
        raw = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self._lock:
            self._conn.execute(
                "INSERT INTO api_tokens (name, token_hash, token_prefix, created_at) VALUES (?, ?, ?, ?)",
                (label, digest, raw[:8], _now()),
            )
            self._conn.commit()
        return raw

    def revoke_api_token(self, token_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM api_tokens WHERE id = ? AND name != 'helm'", (token_id,))
            self._conn.commit()

    def api_token_matches(self, presented: str, api_token: str) -> bool:
        raw = (presented or "").strip()
        if not raw:
            return False
        expected = (api_token or "").strip()
        if expected and hmac.compare_digest(raw, expected):
            return True
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM api_tokens WHERE token_hash = ?",
                (digest,),
            ).fetchone()
        return row is not None
