"""Shared internal typing protocols and aliases."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class HttpClientProtocol(Protocol):
    async def request(self, method: str, path: str, **kwargs: Any) -> Any: ...


class StompClientProtocol(Protocol):
    async def subscribe(self, destination: str) -> str: ...

    async def unsubscribe(self, handle: str) -> None: ...

    async def send(self, destination: str, body: object) -> None: ...


TaskFactory = Callable[[Awaitable[Any]], Any]
