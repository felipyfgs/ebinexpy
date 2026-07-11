import asyncio

import pytest

from ebinexpy.transport.stomp import StompFrame
from ebinexpy.transport.supervisor import ConnectionSupervisor, SubscriptionRegistry


def test_registry_deduplicates_and_reference_counts() -> None:
    registry = SubscriptionRegistry()
    first, created = registry.acquire("/topic/one")
    second, created_again = registry.acquire("/topic/one")
    assert created is True
    assert created_again is False
    assert first is second
    assert registry.release(first.handle)[1] is False
    assert registry.release(first.handle)[1] is True


def test_registry_remote_ids_do_not_collide_after_churn() -> None:
    registry = SubscriptionRegistry()
    first, _ = registry.acquire("/topic/one")
    second, _ = registry.acquire("/topic/two")
    registry.release(first.handle)
    third, _ = registry.acquire("/topic/three")

    assert second.remote_id != third.remote_id


class FakeSocket:
    def __init__(self, fail_receive: bool = False) -> None:
        self.connected = False
        self.sent: list[StompFrame] = []
        self.fail_receive = fail_receive
        self.closed = False
        self.heartbeats = 0

    async def connect(self, _token: str) -> None:
        self.connected = True

    async def send(self, frame: StompFrame) -> None:
        self.sent.append(frame)

    async def receive(self) -> tuple[StompFrame, ...]:
        if self.fail_receive:
            self.fail_receive = False
            raise RuntimeError("lost")
        await asyncio.sleep(60)
        return ()

    async def heartbeat(self) -> None:
        self.heartbeats += 1

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_reconnect_replays_subscriptions_before_ready() -> None:
    sockets: list[FakeSocket] = []

    def factory() -> FakeSocket:
        socket = FakeSocket(fail_receive=not sockets)
        sockets.append(socket)
        return socket

    supervisor = ConnectionSupervisor(
        factory,
        lambda: "token",
        lambda _frame: asyncio.sleep(0),
        heartbeat_interval=10,
        reconnect_attempts=2,
        base_delay=0,
        max_delay=0,
        jitter=0,
    )
    await supervisor.subscribe("/user/topic/TEST")
    await supervisor.subscribe("/user/topic/execute")
    await supervisor.start()
    for _ in range(100):
        if len(sockets) >= 2 and supervisor.ready:
            break
        await asyncio.sleep(0.001)

    assert [frame.headers["destination"] for frame in sockets[1].sent] == [
        "/user/topic/TEST",
        "/user/topic/execute",
    ]
    await supervisor.stop()


@pytest.mark.asyncio
async def test_heartbeat_is_sent_periodically_while_receive_is_silent() -> None:
    socket = FakeSocket()
    supervisor = ConnectionSupervisor(
        lambda: socket,
        lambda: "token",
        lambda _frame: asyncio.sleep(0),
        heartbeat_interval=0.01,
        reconnect_attempts=0,
        base_delay=0,
        max_delay=0,
        jitter=0,
    )

    await supervisor.start()
    await asyncio.sleep(0.025)

    assert socket.heartbeats >= 2
    await supervisor.stop()
