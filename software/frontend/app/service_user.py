"""Usuario local de servicio. Llamar despues de crear el schema."""

from __future__ import annotations

from app.config import settings


def ensure_service_user(users) -> None:
    username = (settings.service_user or "admin").strip() or "admin"
    password = (settings.service_password or "change-me").strip()
    if len(password) < 6:
        raise ValueError("SERVICE_PASSWORD debe tener al menos 6 caracteres.")
    existing = users.find_by_username(username)
    if existing is None:
        users.create_local(username, password, "admin")
        return
    if str(existing.get("auth_type") or "local") != "local":
        return
    users.update(int(existing["id"]), "admin", password)
