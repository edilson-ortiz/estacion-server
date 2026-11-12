"""Cliente HTTP compartido y caché en memoria para llamadas a servicios externos.

Reutilizar un solo `httpx.AsyncClient` evita abrir una conexión TLS nueva en cada request.
"""
import time
from typing import Any, Awaitable, Callable, Hashable

import httpx

from app.core.config import settings

_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS)
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class TTLCache:
    """Caché simple clave→valor con expiración. Solo guarda resultados exitosos."""

    def __init__(self, ttl_seconds: int, max_items: int = 1000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: dict[Hashable, tuple[float, Any]] = {}

    async def get_or_set(self, key: Hashable, factory: Callable[[], Awaitable[Any]]) -> Any:
        if self.ttl <= 0:
            return await factory()

        now = time.monotonic()
        hit = self._data.get(key)
        if hit and hit[0] > now:
            return hit[1]

        value = await factory()

        if len(self._data) >= self.max_items:
            self._data = {k: v for k, v in self._data.items() if v[0] > now}
            if len(self._data) >= self.max_items:
                self._data.pop(next(iter(self._data)))
        self._data[key] = (now + self.ttl, value)
        return value
