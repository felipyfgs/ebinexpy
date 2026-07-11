"""Persistent authenticated HTTP transport."""

from collections.abc import Callable
from typing import Any

import httpx

from ..core.exceptions import AuthenticationError, TransportError
from ..core.logging import redact_text


class HttpTransport:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        token: Callable[[], str | None],
        account_id: Callable[[], str | None],
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self._account_id = account_id
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            verify=True,
            headers={"Accept": "application/json", "x-tenant": "ebinex"},
        )

    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json", "x-tenant": "ebinex"}
        if token := self._token():
            headers["Authorization"] = f"Bearer {token}"
        if account_id := self._account_id():
            headers["accountid"] = account_id
        return headers

    async def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = {**self.headers(), **kwargs.pop("headers", {})}
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise TransportError(redact_text(f"HTTP {method} {path} failed: {exc}")) from exc
        if response.status_code == 401:
            raise AuthenticationError("Broker rejected the authenticated request")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TransportError(
                redact_text(f"HTTP {method} {path} returned {response.status_code}")
            ) from exc
        return response

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
