from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class BackendClient:
    def __init__(self) -> None:
        self.base = settings.backend_url.rstrip("/")
        self.headers = {}
        if settings.api_token:
            self.headers["Authorization"] = f"Bearer {settings.api_token}"

    async def get_json(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.base}{path}", headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def post_json(self, path: str, payload: dict[str, Any], timeout: float = 20.0) -> Any:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base}{path}", headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def delete(self, path: str) -> None:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(f"{self.base}{path}", headers=self.headers)
            response.raise_for_status()
