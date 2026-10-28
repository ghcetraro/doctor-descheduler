from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from app.config import Settings


class OidcClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._endpoints: Optional[dict[str, str]] = None

    def is_configured(self) -> bool:
        if not self.settings.oidc_enabled:
            return False
        return all(
            [
                self.settings.oidc_issuer,
                self.settings.oidc_client_id,
                self.settings.oidc_client_secret,
            ]
        )

    def redirect_uri(self, request_host: str, forwarded_proto: str) -> str:
        if self.settings.oidc_redirect_uri:
            return self.settings.oidc_redirect_uri
        scheme = forwarded_proto or "http"
        return f"{scheme}://{request_host}/oidc/callback"

    async def auth_url(self, state: str, redirect_uri: str) -> str:
        endpoints = await self._resolve_endpoints()
        params = urlencode(
            {
                "client_id": self.settings.oidc_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": self.settings.oidc_scopes,
                "state": state,
            }
        )
        return f"{endpoints['authorization_endpoint']}?{params}"

    async def user_from_code(self, code: str, redirect_uri: str) -> Optional[dict[str, str]]:
        endpoints = await self._resolve_endpoints()
        async with httpx.AsyncClient(timeout=20.0) as client:
            token_resp = await client.post(
                endpoints["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.settings.oidc_client_id,
                    "client_secret": self.settings.oidc_client_secret,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code >= 400:
                return None
            access_token = token_resp.json().get("access_token")
            if not access_token:
                return None
            user_resp = await client.get(
                endpoints["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            if user_resp.status_code >= 400:
                return None
            info: dict[str, Any] = user_resp.json()
        sub = str(info.get("sub", "")).strip()
        email = str(info.get("email", "")).strip().lower()
        name = str(info.get("name") or info.get("preferred_username") or email).strip()
        groups_raw = info.get("groups") or []
        groups = [str(item).strip() for item in groups_raw] if isinstance(groups_raw, list) else []
        if not sub or not email:
            return None
        return {"sub": sub, "email": email, "name": name, "groups": groups}

    def resolve_role(self, groups: list[str]) -> str:
        allowed = {item.strip().lower() for item in self.settings.oidc_admin_groups.split(",") if item.strip()}
        names = {item.strip().lower() for item in groups if item.strip()}
        if allowed & names:
            return "admin"
        return "readonly"

    async def _resolve_endpoints(self) -> dict[str, str]:
        if self._endpoints is not None:
            return self._endpoints
        discovery = f"{self.settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(discovery)
            resp.raise_for_status()
            data = resp.json()
        self._endpoints = {
            "authorization_endpoint": data["authorization_endpoint"],
            "token_endpoint": data["token_endpoint"],
            "userinfo_endpoint": data["userinfo_endpoint"],
        }
        return self._endpoints
