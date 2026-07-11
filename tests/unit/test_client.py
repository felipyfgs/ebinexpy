import asyncio

import httpx
import pytest

from ebinexpy import ClientConfig, EbinexClient
from ebinexpy.accounts import AccountEnvironment
from ebinexpy.core import AuthenticationError, ConnectionError, RealTradingDisabledError
from ebinexpy.transport.stomp import StompFrame


class FakeSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.connected = False
        self.fail = fail
        self.closed = False
        self.sent: list[StompFrame] = []

    async def connect(self, _token: str) -> None:
        if self.fail:
            raise RuntimeError("cannot connect")
        self.connected = True

    async def send(self, frame: StompFrame) -> None:
        self.sent.append(frame)

    async def receive(self) -> tuple[StompFrame, ...]:
        await asyncio.sleep(60)
        return ()

    async def heartbeat(self) -> None: ...

    async def close(self) -> None:
        self.closed = True


def broker_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/auth/login":
        return httpx.Response(
            200,
            json={
                "token": "session-token",
                "accounts": [{"id": "test-id", "environment": "TEST"}],
            },
        )
    if request.url.path == "/users/listAccounts":
        assert request.headers["accountid"] == "test-id"
        return httpx.Response(
            200,
            json=[
                {"id": "test-id", "environment": "TEST", "balance": "10.25"},
                {"id": "real-id", "environment": "REAL", "balance": "1"},
            ],
        )
    if request.url.path == "/users":
        return httpx.Response(200, json={"id": "user", "email": "placeholder"})
    raise AssertionError(request.url.path)


@pytest.mark.asyncio
async def test_facade_connect_switch_disconnect_and_logout() -> None:
    socket = FakeSocket()
    transport = httpx.MockTransport(broker_handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.ebinex.com"
    ) as http_client:
        client = EbinexClient(
            "identity", "password", http_client=http_client, socket_factory=lambda: socket
        )
        await client.connect()
        await client.connect()
        assert client.connected
        assert [frame.headers.get("destination") for frame in socket.sent] == [
            "/user/topic/TEST",
            "/user/topic/execute",
        ]

        await client.select_account(AccountEnvironment.REAL)
        assert client.accounts.selected.environment is AccountEnvironment.REAL
        assert socket.sent[-2].headers["destination"] == "/user/topic/REAL"
        assert socket.sent[-1].command == "UNSUBSCRIBE"
        with pytest.raises(RealTradingDisabledError):
            await client.raw.send("/user/topic/execute", {})

        await client.logout()
        assert socket.closed
        assert not client.authenticated
        assert await client.config.session_store.load("identity") is None


@pytest.mark.asyncio
async def test_safe_request_reauthenticates_once_but_unsafe_does_not() -> None:
    calls = {"login": 0, "users": 0, "unsafe": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            calls["login"] += 1
            return httpx.Response(200, json={"token": f"token-{calls['login']}"})
        if request.url.path == "/users":
            calls["users"] += 1
            if calls["users"] == 1:
                return httpx.Response(401)
            return httpx.Response(200, json={"id": "user"})
        calls["unsafe"] += 1
        return httpx.Response(401)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.ebinex.com"
    ) as http_client:
        client = EbinexClient("identity", "password", http_client=http_client)
        await client.auth.ensure(client._credentials)  # noqa: SLF001
        profile = await client.get_profile()
        assert profile.id == "user"
        assert calls["login"] == 2
        with pytest.raises(AuthenticationError):
            await client.raw.request("POST", "/unsafe")
        assert calls["unsafe"] == 1


@pytest.mark.asyncio
async def test_connect_rolls_back_when_socket_fails() -> None:
    transport = httpx.MockTransport(broker_handler)
    config = ClientConfig(reconnect_attempts=0, connect_timeout=0.5)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.ebinex.com"
    ) as http_client:
        client = EbinexClient(
            "identity",
            "password",
            config,
            http_client=http_client,
            socket_factory=lambda: FakeSocket(fail=True),
        )
        with pytest.raises(ConnectionError):
            await client.connect()
        assert not client.connected
        assert client._supervisor is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_reconnect_exhaustion_clears_public_state_and_wakes_waiters() -> None:
    transport = httpx.MockTransport(broker_handler)
    config = ClientConfig(
        reconnect_attempts=1,
        reconnect_base_delay=0,
        reconnect_max_delay=0,
        reconnect_jitter=0,
        connect_timeout=0.5,
    )

    fail_connections = asyncio.Event()

    def factory() -> FakeSocket:
        socket = FakeSocket()

        async def fail_receive() -> tuple[StompFrame, ...]:
            await fail_connections.wait()
            raise RuntimeError("connection lost")

        socket.receive = fail_receive  # type: ignore[method-assign]
        return socket

    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.ebinex.com"
    ) as http_client:
        client = EbinexClient(
            "identity",
            "password",
            config,
            http_client=http_client,
            socket_factory=factory,
        )
        await client.connect()
        fail_connections.set()
        for _ in range(100):
            if not client.connected:
                break
            await asyncio.sleep(0.001)

        assert not client.connected
        with pytest.raises(ConnectionError, match="budget exhausted"):
            await client.wait_until_ready(timeout=0.1)
        await client.disconnect()


@pytest.mark.asyncio
async def test_connect_during_reconnect_reuses_the_running_supervisor() -> None:
    transport = httpx.MockTransport(broker_handler)
    config = ClientConfig(
        reconnect_attempts=2,
        reconnect_base_delay=0,
        reconnect_max_delay=0,
        reconnect_jitter=0,
        connect_timeout=0.5,
    )
    fail_first = asyncio.Event()
    allow_reconnect = asyncio.Event()
    sockets_created = 0

    def factory() -> FakeSocket:
        nonlocal sockets_created
        sockets_created += 1
        socket = FakeSocket()
        if sockets_created == 1:

            async def fail_receive() -> tuple[StompFrame, ...]:
                await fail_first.wait()
                raise RuntimeError("connection lost")

            socket.receive = fail_receive  # type: ignore[method-assign]
        else:
            connect = socket.connect

            async def delayed_connect(token: str) -> None:
                await allow_reconnect.wait()
                await connect(token)

            socket.connect = delayed_connect  # type: ignore[method-assign]
        return socket

    async with httpx.AsyncClient(
        transport=transport, base_url="https://api.ebinex.com"
    ) as http_client:
        client = EbinexClient(
            "identity",
            "password",
            config,
            http_client=http_client,
            socket_factory=factory,
        )
        await client.connect()
        fail_first.set()
        for _ in range(100):
            if not client.connected and sockets_created == 2:
                break
            await asyncio.sleep(0.001)

        reconnect = asyncio.create_task(client.connect())
        await asyncio.sleep(0)
        assert sockets_created == 2

        allow_reconnect.set()
        await reconnect
        assert client.connected
        assert sockets_created == 2
        await client.disconnect()
