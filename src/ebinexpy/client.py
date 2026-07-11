"""Composition root for the public Ebinex client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from .accounts.models import Account, AccountEnvironment, Balance, Profile
from .accounts.service import AccountService
from .auth.models import Credentials
from .auth.service import AuthService
from .config import ClientConfig
from .core.exceptions import AuthenticationError, ConnectionError, NotConnectedError
from .events.dispatcher import EventDispatcher
from .events.models import (
    BookEvent,
    CandleEvent,
    ConnectionEvent,
    ConnectionState,
    TickerEvent,
)
from .events.streams import EventStream
from .market.models import Asset, BrokerTime, Candle, Timeframe
from .market.service import MarketService
from .orders.models import Order, OrderQuery, OrderRequest, Settlement
from .orders.service import OrderService
from .raw.client import RawClient
from .transport.http import HttpTransport
from .transport.stomp import StompFrame
from .transport.supervisor import ConnectionSupervisor, Socket, SupervisorState
from .transport.websocket import WebSocketTransport

SocketFactory = Callable[[], Socket]


class EbinexClient:
    """Async-first facade over the Ebinex traderoom protocol.

    Credentials are kept outside :class:`ClientConfig` so configuration can be
    safely logged or shared. No connection is opened by the constructor.
    """

    def __init__(
        self,
        email: str = "",
        password: str = "",
        config: ClientConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        socket_factory: SocketFactory | None = None,
    ) -> None:
        self.config = config or ClientConfig()
        self._credentials = Credentials(email=email, password=password)
        self._socket_factory = socket_factory
        self._supervisor: ConnectionSupervisor | None = None
        self._core_user_handle: str | None = None
        self._core_environment: AccountEnvironment | None = None
        self._execute_handle: str | None = None
        self._connect_lock = asyncio.Lock()
        self._ready = asyncio.Event()
        self._connection_changed = asyncio.Event()
        self._connection_error: ConnectionError | None = None

        self.events = EventDispatcher()
        self.auth = AuthService(self)
        self.accounts = AccountService(self)
        self.market = MarketService(self)
        self.orders = OrderService(self)
        self.raw = RawClient(self)
        self._http = HttpTransport(
            self.config.http_base_url,
            self.config.request_timeout,
            token=lambda: self.auth.session.access_token if self.auth.session else None,
            account_id=lambda: (
                self.accounts.selected.id
                if self.accounts.selected
                else self.auth.session.account_id
                if self.auth.session
                else None
            ),
            client=http_client,
        )

    @property
    def authenticated(self) -> bool:
        return self.auth.authenticated

    @property
    def connected(self) -> bool:
        return self._ready.is_set()

    async def _request(
        self, method: str, path: str, *, retry_auth: bool = True, **kwargs: Any
    ) -> httpx.Response:
        """Perform REST I/O, retrying an authentication failure only when safe."""
        try:
            return await self._http.request(method, path, **kwargs)
        except AuthenticationError:
            if not retry_auth:
                raise
            self.auth.session = None
            await self.config.session_store.delete(self._credentials.email)
            await self.auth.ensure(self._credentials)
            return await self._http.request(method, path, **kwargs)

    def _make_socket(self) -> Socket:
        if self._socket_factory is not None:
            return self._socket_factory()
        return WebSocketTransport(
            self.config.websocket_base_url,
            self.config.connect_timeout,
            self.config.heartbeat_interval,
        )

    def _on_connection_state(
        self,
        state: SupervisorState,
        attempt: int,
        error: ConnectionError | None,
    ) -> None:
        now = datetime.now(UTC)
        if state is SupervisorState.CONNECTED:
            self._connection_error = None
            self._ready.set()
            self.events.emit(ConnectionEvent(now, ConnectionState.CONNECTED))
        elif state is SupervisorState.RECONNECTING:
            self._ready.clear()
            self.events.emit(ConnectionEvent(now, ConnectionState.RECONNECTING, attempt))
        else:
            self._ready.clear()
            self._connection_error = error or ConnectionError("WebSocket disconnected")
            self.events.emit(ConnectionEvent(now, ConnectionState.DISCONNECTED, attempt))
        self._connection_changed.set()

    async def connect(self) -> None:
        """Authenticate, select the configured account and start live transport."""
        async with self._connect_lock:
            if self.connected:
                return
            if self._supervisor is not None and self._supervisor.running:
                await self.wait_until_ready(timeout=self.config.connect_timeout)
                return
            self._connection_error = None
            self.events.emit(ConnectionEvent(datetime.now(UTC), ConnectionState.CONNECTING))
            await self.auth.ensure(self._credentials)
            await self.accounts.select(self.config.environment)
            self._supervisor = ConnectionSupervisor(
                self._make_socket,
                token=lambda: self.auth.session.access_token if self.auth.session else "",
                on_frame=self._on_frame,
                on_state=self._on_connection_state,
                heartbeat_interval=self.config.heartbeat_interval,
                reconnect_attempts=self.config.reconnect_attempts,
                base_delay=self.config.reconnect_base_delay,
                max_delay=self.config.reconnect_max_delay,
                jitter=self.config.reconnect_jitter,
            )
            try:
                self._core_user_handle = await self._supervisor.subscribe(
                    self._user_destination(self.config.environment)
                )
                self._core_environment = self.config.environment
                self._execute_handle = await self._supervisor.subscribe("/user/topic/execute")
                await asyncio.wait_for(
                    self._supervisor.start(), timeout=self.config.connect_timeout
                )
            except BaseException:
                if self._supervisor is not None:
                    await self._supervisor.stop()
                self._supervisor = None
                self._core_user_handle = None
                self._core_environment = None
                self._execute_handle = None
                if self._connection_error is None:
                    self.events.emit(
                        ConnectionEvent(datetime.now(UTC), ConnectionState.DISCONNECTED)
                    )
                raise

    @staticmethod
    def _user_destination(environment: AccountEnvironment) -> str:
        return f"/user/topic/{environment.value}"

    async def _account_selected(self, account: Account) -> None:
        if self._supervisor is None or not self._supervisor.ready:
            return
        if account.environment is self._core_environment:
            return
        self._ready.clear()
        try:
            new_handle = await self._supervisor.subscribe(
                self._user_destination(account.environment)
            )
            old_handle, self._core_user_handle = self._core_user_handle, new_handle
            self._core_environment = account.environment
            if old_handle and old_handle != new_handle:
                await self._supervisor.unsubscribe(old_handle)
        finally:
            if self._supervisor.ready:
                self._ready.set()
                self._connection_changed.set()

    async def _on_frame(self, frame: StompFrame) -> None:
        if frame.command != "MESSAGE":
            return
        self.raw.handle_frame(frame)
        try:
            payload = json.loads(frame.body) if frame.body else {}
        except json.JSONDecodeError:
            return
        destination = frame.headers.get("destination", "")
        await self.accounts.handle_event(destination, payload)
        await self.market.handle_event(destination, payload)
        await self.orders.handle_event(destination, payload)

    async def wait_until_ready(self, timeout: float | None = None) -> None:  # noqa: ASYNC109
        async def wait() -> None:
            while not self._ready.is_set():
                if self._connection_error is not None:
                    raise self._connection_error
                self._connection_changed.clear()
                if self._ready.is_set() or self._connection_error is not None:
                    continue
                await self._connection_changed.wait()

        if timeout is None:
            await wait()
        else:
            await asyncio.wait_for(wait(), timeout)

    def require_supervisor(self) -> ConnectionSupervisor:
        if self._supervisor is None or not self._supervisor.ready:
            raise NotConnectedError("EbinexClient is not connected")
        return self._supervisor

    async def disconnect(self) -> None:
        """Stop live transport. Calling this repeatedly is safe."""
        async with self._connect_lock:
            self._ready.clear()
            self._connection_error = None
            self._connection_changed.set()
            supervisor, self._supervisor = self._supervisor, None
            self._core_user_handle = None
            self._core_environment = None
            self._execute_handle = None
            if supervisor is not None:
                await supervisor.stop()
                self.events.emit(ConnectionEvent(datetime.now(UTC), ConnectionState.DISCONNECTED))

    async def logout(self) -> None:
        """Disconnect and delete only this identity's stored session."""
        await self.disconnect()
        await self.auth.logout(self._credentials.email)
        await self._http.close()

    async def close(self) -> None:
        await self.disconnect()
        await self._http.close()
        await self.events.close()

    async def __aenter__(self) -> EbinexClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # Stable convenience surface. Feature services remain available for
    # advanced consumers that need their caches or stream controls directly.
    async def list_accounts(self) -> list[Account]:
        return await self.accounts.list()

    async def select_account(self, environment: AccountEnvironment) -> Account:
        return await self.accounts.select(environment)

    async def get_profile(self) -> Profile:
        return await self.accounts.profile()

    async def get_balance(self) -> Balance:
        return await self.accounts.balance()

    async def list_assets(self, *, refresh: bool = False) -> list[Asset]:
        return await self.market.list_assets(refresh=refresh)

    async def get_asset(self, symbol: str, *, refresh: bool = False) -> Asset:
        return await self.market.get_asset(symbol, refresh=refresh)

    async def get_payout(self, symbol: str, timeframe: Timeframe) -> Decimal:
        return await self.market.get_payout(symbol, timeframe)

    async def is_market_open(self, symbol: str, timeframe: Timeframe) -> bool:
        return await self.market.is_market_open(symbol, timeframe)

    def get_broker_time(self) -> BrokerTime | None:
        return self.market.get_broker_time()

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        return await self.market.get_candles(symbol, timeframe, start, end, limit=limit)

    async def stream_candles(self, symbol: str, timeframe: Timeframe) -> EventStream[CandleEvent]:
        return await self.market.stream_candles(symbol, timeframe)

    async def stream_ticker(self, symbol: str, timeframe: Timeframe) -> EventStream[TickerEvent]:
        return await self.market.stream_ticker(symbol, timeframe)

    async def stream_book(self, symbol: str, timeframe: Timeframe) -> EventStream[BookEvent]:
        return await self.market.stream_book(symbol, timeframe)

    async def place_order(self, request: OrderRequest) -> Order:
        return await self.orders.place(request)

    async def list_orders(self, query: OrderQuery | None = None) -> list[Order]:
        return await self.orders.list(query)

    async def get_order(self, order_id: str, *, refresh: bool = False) -> Order | None:
        return await self.orders.get(order_id, refresh=refresh)

    async def wait_order(
        self,
        order_id: str,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> Settlement:
        return await self.orders.wait(order_id, timeout)
