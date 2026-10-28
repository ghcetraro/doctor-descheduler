"""Usuario de servicio local (sin OIDC) para pruebas de agentes.

Copiar `ensure_service_user` al store de usuarios y llamarlo en el arranque
(lifespan / startup), después de crear el schema, aunque ya existan usuarios OIDC.

Env:
  SERVICE_USER      default admin
  SERVICE_PASSWORD  default change-me (mínimo 6 caracteres)

El store debe exponer find_by_username, create_local(username, password, role)
y update(user_id, role, password).
"""

from __future__ import annotations

import os

SERVICE_USER = os.getenv("SERVICE_USER", "admin").strip() or "admin"
SERVICE_PASSWORD = os.getenv("SERVICE_PASSWORD", "change-me")


def ensure_service_user(users) -> None:
    username = SERVICE_USER
    password = SERVICE_PASSWORD.strip()
    if len(password) < 6:
        raise ValueError("SERVICE_PASSWORD debe tener al menos 6 caracteres.")
    existing = users.find_by_username(username)
    if existing is None:
        users.create_local(username, password, "admin")
        return
    if str(existing.get("auth_type") or "local") != "local":
        return
    users.update(int(existing["id"]), "admin", password)
