"""Connection supervision and subscription restoration."""

import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
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


class SupervisorState(StrEnum):
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DISCONNECTED = "DISCONNECTED"


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
        subscription = Subscription(handle, destination, remote_id=f"sub-{self._counter - 1}")
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
StateHandler = Callable[[SupervisorState, int, ConnectionError | None], None]


class ConnectionSupervisor:
    def __init__(
        self,
        socket_factory: Callable[[], Socket],
        token: Callable[[], str],
        on_frame: FrameHandler,
        on_state: StateHandler | None = None,
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
        self._on_state = on_state
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
        self._terminal_error: ConnectionError | None = None
        self._reconnect_failures = 0

    @property
    def ready(self) -> bool:
        return self._ready.is_set()

    @property
    def running(self) -> bool:
        return self._runner is not None and not self._runner.done()

    @property
    def terminal_error(self) -> ConnectionError | None:
        return self._terminal_error

    def _notify(
        self, state: SupervisorState, attempt: int = 0, error: ConnectionError | None = None
    ) -> None:
        if self._on_state is not None:
            self._on_state(state, attempt, error)

    @staticmethod
    def _consume_runner_result(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    async def start(self) -> None:
        if self._runner and not self._runner.done():
            return
        self._stopping = False
        self._terminal_error = None
        self._reconnect_failures = 0
        self._runner = asyncio.create_task(self._run())
        self._runner.add_done_callback(self._consume_runner_result)
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
        self._socket = socket
        await socket.connect(self._token())
        for subscription in self._registry.active():
            assert subscription.remote_id is not None
            await socket.send(
                StompFrame(
                    "SUBSCRIBE",
                    {"id": subscription.remote_id, "destination": subscription.destination},
                )
            )
        self._ready.set()
        self._notify(SupervisorState.CONNECTED)

    async def _receive_loop(self, socket: Socket) -> None:
        while True:
            frames = await asyncio.wait_for(socket.receive(), timeout=self._heartbeat_interval * 3)
            self._reconnect_failures = 0
            for frame in frames:
                await self._on_frame(frame)

    async def _heartbeat_loop(self, socket: Socket) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            await socket.heartbeat()

    async def _connected_session(self, socket: Socket) -> None:
        async with asyncio.TaskGroup() as group:
            group.create_task(self._receive_loop(socket))
            group.create_task(self._heartbeat_loop(socket))

    async def _run(self) -> None:
        while not self._stopping:
            try:
                if self._socket is None:
                    await self._connect()
                assert self._socket is not None
                await self._connected_session(self._socket)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._ready.clear()
                if self._socket:
                    await self._socket.close()
                self._socket = None
                self._reconnect_failures += 1
                if self._reconnect_failures > self._reconnect_attempts:
                    error = ConnectionError("WebSocket reconnect budget exhausted")
                    self._terminal_error = error
                    self._notify(SupervisorState.DISCONNECTED, self._reconnect_failures, error)
                    raise error from exc
                self._notify(SupervisorState.RECONNECTING, self._reconnect_failures)
                delay = min(
                    self._base_delay * (2 ** (self._reconnect_failures - 1)),
                    self._max_delay,
                )
                delay *= 1 + random.uniform(-self._jitter, self._jitter)
                await asyncio.sleep(max(0, delay))

    async def subscribe(self, destination: str) -> str:
        subscription, created = self._registry.acquire(destination)
        if created and self._socket and self.ready:
            assert subscription.remote_id is not None
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
