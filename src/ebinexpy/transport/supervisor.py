"""Connection supervision and subscription restoration."""

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from ..core.exceptions import ConnectionError, NotConnectedError
from .stomp import StompFrame


class Socket(Protocol):
    connected: bool

    async def connect(self, token: str) -> None: ...
    async def send(self, frame: StompFrame) -> None: ...
    async def receive(self) -> tuple[StompFrame, ...]: ...
    async def heartbeat(self) -> None: ...
    async def close(self) -> None: ...


@dataclass(slots=True)
class Subscription:
    handle: str
    destination: str
    references: int = 1
    remote_id: str | None = None


class SubscriptionRegistry:
    def __init__(self) -> None:
        self._counter = 0
        self._by_destination: dict[str, Subscription] = {}
        self._by_handle: dict[str, Subscription] = {}

    def acquire(self, destination: str) -> tuple[Subscription, bool]:
        if subscription := self._by_destination.get(destination):
            subscription.references += 1
            return subscription, False
        handle = f"subscription-{self._counter}"
        self._counter += 1
        subscription = Subscription(handle, destination)
        self._by_destination[destination] = subscription
        self._by_handle[handle] = subscription
        return subscription, True

    def release(self, handle: str) -> tuple[Subscription | None, bool]:
        subscription = self._by_handle.get(handle)
        if subscription is None:
            return None, False
        subscription.references -= 1
        if subscription.references:
            return subscription, False
        self._by_handle.pop(handle)
        self._by_destination.pop(subscription.destination)
        return subscription, True

    def active(self) -> tuple[Subscription, ...]:
        return tuple(self._by_destination.values())


FrameHandler = Callable[[StompFrame], Awaitable[None]]


class ConnectionSupervisor:
    def __init__(
        self,
        socket_factory: Callable[[], Socket],
        token: Callable[[], str],
        on_frame: FrameHandler,
        *,
        heartbeat_interval: float,
        reconnect_attempts: int,
        base_delay: float,
        max_delay: float,
        jitter: float,
    ) -> None:
        self._socket_factory = socket_factory
        self._token = token
        self._on_frame = on_frame
        self._heartbeat_interval = heartbeat_interval
        self._reconnect_attempts = reconnect_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._jitter = jitter
        self._socket: Socket | None = None
        self._registry = SubscriptionRegistry()
        self._runner: asyncio.Task[None] | None = None
        self._stopping = False
        self._ready = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        self._stopping = False
        self._runner = asyncio.create_task(self._run())
        ready_waiter = asyncio.create_task(self._ready.wait())
        done, _ = await asyncio.wait(
            {ready_waiter, self._runner}, return_when=asyncio.FIRST_COMPLETED
        )
        if self._runner in done and not self._ready.is_set():
            ready_waiter.cancel()
            await asyncio.gather(ready_waiter, return_exceptions=True)
            await self._runner
        ready_waiter.cancel()
        await asyncio.gather(ready_waiter, return_exceptions=True)

    async def _connect(self) -> None:
        socket = self._socket_factory()
        await socket.connect(self._token())
        self._socket = socket
        for index, subscription in enumerate(self._registry.active()):
            remote_id = f"sub-{index}"
            subscription.remote_id = remote_id
            await socket.send(
                StompFrame("SUBSCRIBE", {"id": remote_id, "destination": subscription.destination})
            )
        self._ready.set()

    async def _run(self) -> None:
        attempts = 0
        while not self._stopping:
            try:
                if self._socket is None:
                    await self._connect()
                    attempts = 0
                assert self._socket is not None
                frames = await asyncio.wait_for(
                    self._socket.receive(), timeout=self._heartbeat_interval * 3
                )
                for frame in frames:
                    await self._on_frame(frame)
            except TimeoutError:
                if self._socket:
                    await self._socket.heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._ready.clear()
                if self._socket:
                    await self._socket.close()
                self._socket = None
                attempts += 1
                if attempts > self._reconnect_attempts:
                    raise ConnectionError("WebSocket reconnect budget exhausted") from exc
                delay = min(self._base_delay * (2 ** (attempts - 1)), self._max_delay)
                delay *= 1 + random.uniform(-self._jitter, self._jitter)
                await asyncio.sleep(max(0, delay))

    async def subscribe(self, destination: str) -> str:
        subscription, created = self._registry.acquire(destination)
        if created and self._socket and self.ready:
            subscription.remote_id = f"sub-{len(self._registry.active()) - 1}"
            await self._socket.send(
                StompFrame(
                    "SUBSCRIBE",
                    {"id": subscription.remote_id, "destination": subscription.destination},
                )
            )
        return subscription.handle

    async def unsubscribe(self, handle: str) -> None:
        subscription, removed = self._registry.release(handle)
        if removed and subscription and subscription.remote_id and self._socket and self.ready:
            await self._socket.send(StompFrame("UNSUBSCRIBE", {"id": subscription.remote_id}))

    async def send(self, destination: str, body: object) -> None:
        if not self._socket or not self.ready:
            raise NotConnectedError("WebSocket is not ready")
        await self._socket.send(
            StompFrame(
                "SEND",
                {"destination": destination, "content-type": "application/json"},
                json.dumps(body, separators=(",", ":"), default=str),
            )
        )

    async def stop(self) -> None:
        self._stopping = True
        self._ready.clear()
        if self._runner:
            self._runner.cancel()
            await asyncio.gather(self._runner, return_exceptions=True)
            self._runner = None
        if self._socket:
            await self._socket.close()
            self._socket = None
