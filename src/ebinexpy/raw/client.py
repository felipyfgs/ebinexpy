"""Explicitly unstable raw protocol facade."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from ..accounts.models import AccountEnvironment
from ..events.streams import EventStream
from ..orders.validation import guard_environment
from ..transport.stomp import StompFrame
from ..transport.supervisor import ConnectionSupervisor

if TYPE_CHECKING:
    from ..client import EbinexClient


@dataclass(slots=True)
class RawSubscription:
    """Bounded message stream and cleanup handle for an unstable destination."""

    _supervisor: ConnectionSupervisor
    handle: str
    destination: str
    _stream: EventStream[StompFrame]
    _closed: bool = False

    def __aiter__(self) -> AsyncIterator[StompFrame]:
        return self._stream

    async def __anext__(self) -> StompFrame:
        return await self._stream.__anext__()

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._stream.close()

    async def __aenter__(self) -> RawSubscription:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


class RawClient:
    """Unstable REST/STOMP access that cannot bypass lifecycle or REAL guards."""

    def __init__(self, client: EbinexClient) -> None:
        self._client = client
        self._streams: dict[str, set[EventStream[StompFrame]]] = {}

    async def request(
        self,
        method: str,
        path: str,
        *,
        retry_auth: bool | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        safe = method.upper() in {"GET", "HEAD", "OPTIONS"} if retry_auth is None else retry_auth
        if path.rstrip("/").endswith("/orders") and method.upper() != "GET":
            safe = False
        return await self._client._request(  # noqa: SLF001
            method, path, retry_auth=safe, **kwargs
        )

    async def subscribe(self, destination: str) -> RawSubscription:
        supervisor = self._client.require_supervisor()
        handle = await supervisor.subscribe(destination)
        stream: EventStream[StompFrame]

        async def cleanup() -> None:
            self._streams.get(destination, set()).discard(stream)
            if not self._streams.get(destination):
                self._streams.pop(destination, None)
            await supervisor.unsubscribe(handle)

        stream = EventStream(
            self._client.config.event_queue_size,
            cleanup=cleanup,
        )
        self._streams.setdefault(destination, set()).add(stream)
        return RawSubscription(supervisor, handle, destination, stream)

    async def send(self, destination: str, body: object) -> None:
        if destination.rstrip("/") == "/user/topic/execute":
            selected = self._client.accounts.selected
            environment = selected.environment if selected else AccountEnvironment.REAL
            guard_environment(environment, self._client.config.allow_real_trading)
        await self._client.require_supervisor().send(destination, body)

    def handle_frame(self, frame: StompFrame) -> None:
        destination = frame.headers.get("destination", "")
        for stream in tuple(self._streams.get(destination, ())):
            stream.publish(frame)
