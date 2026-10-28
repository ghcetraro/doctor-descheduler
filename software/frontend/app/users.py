from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from pathlib import Path
from typing import Optional


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"


def _verify(password: str, stored: str) -> bool:
    parts = (stored or "").split("$")
    if len(parts) != 4:
        return False
    _, _iters, salt, _digest = parts
    return secrets.compare_digest(_hash_password(password, salt), stored)


class UserStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              password_hash TEXT,
              role TEXT NOT NULL,
              auth_type TEXT NOT NULL,
              email TEXT,
              oidc_sub TEXT
            )
            """
        )
        self._conn.commit()

    def list_users(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, username, role, auth_type, email FROM users ORDER BY username"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete(self, user_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM users WHERE id = ? AND auth_type = 'local'", (user_id,))
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(row["n"])

    def find_by_username(self, username: str) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, password_hash, role, auth_type, email, oidc_sub FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return dict(row) if row else None

    def verify(self, username: str, password: str) -> Optional[dict]:
        user = self.find_by_username(username)
        if not user or user.get("auth_type") != "local":
            return None
        if not _verify(password, str(user.get("password_hash") or "")):
            return None
        return user

    def create_local(self, username: str, password: str, role: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (username, password_hash, role, auth_type, email)
                VALUES (?, ?, ?, 'local', ?)
                """,
                (username, _hash_password(password), role, f"{username}@local"),
            )
            self._conn.commit()

    def update(self, user_id: int, role: str, password: Optional[str] = None) -> None:
        with self._lock:
            if password:
                self._conn.execute(
                    "UPDATE users SET role = ?, password_hash = ? WHERE id = ?",
                    (role, _hash_password(password), user_id),
                )
            else:
                self._conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            self._conn.commit()

    def upsert_oidc(self, sub: str, email: str, name: str, role: str = "readonly") -> dict:
        role = role if role in {"admin", "readonly"} else "readonly"
        with self._lock:
            row = self._conn.execute(
                "SELECT id, username, role, auth_type, email, oidc_sub FROM users WHERE oidc_sub = ? OR email = ?",
                (sub, email),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO users (username, role, auth_type, email, oidc_sub)
                    VALUES (?, ?, 'oidc', ?, ?)
                    """,
                    (email, role, email, sub),
                )
            elif row["auth_type"] == "oidc":
                self._conn.execute(
                    "UPDATE users SET role = ?, email = ?, oidc_sub = ? WHERE id = ?",
                    (role, email, sub, row["id"]),
                )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT id, username, role, auth_type, email, oidc_sub FROM users WHERE oidc_sub = ? OR email = ?",
                (sub, email),
            ).fetchone()
        user = dict(row)
        user["name"] = name
        return user
