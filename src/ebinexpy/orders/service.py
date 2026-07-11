"""OPTION order feature service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from ..core.exceptions import (
    OrderError,
    OrderRejectedError,
    OrderSubmissionUnknownError,
    ProtocolError,
    SettlementTimeoutError,
    ValidationError,
)
from ..events.models import OrderEvent
from ..market.models import Timeframe
from .models import Order, OrderQuery, OrderRequest, OrderStatus, Settlement
from .state import OrderTracker
from .validation import guard_environment, validate_request
from .wire import TERMINAL_STATUSES, execute_payload, parse_order

if TYPE_CHECKING:
    from ..client import EbinexClient


class OrderService:
    """Coordinates validation, placement, state tracking and history."""

    def __init__(self, client: EbinexClient) -> None:
        self._client = client
        self._submission_lock = asyncio.Lock()
        self._confirmation: asyncio.Future[Order] | None = None
        self._submission_uncertain = False
        self._trackers: dict[str, OrderTracker] = {}

    async def place(self, request: OrderRequest) -> Order:
        account = self._client.accounts.selected
        if account is None:
            raise ValidationError("Select an account before placing an order")
        guard_environment(account.environment, self._client.config.allow_real_trading)
        asset = await self._client.market.get_asset(request.symbol, refresh=True)
        validate_request(request, asset)
        broker = self._client.market.get_broker_time()
        now = broker.value if broker else datetime.now(UTC)
        duration = {"M1": 60_000, "M5": 300_000, "M15": 900_000}[request.timeframe.value]
        now_ms = int(now.timestamp() * 1000)
        boundary = ((now_ms // duration) + 1) * duration
        price = request.price
        if price is None:
            candles = await self._client.market.get_candles(
                request.symbol,
                request.timeframe,
                now - timedelta(milliseconds=duration * 2),
                now,
                limit=1,
            )
            if not candles:
                raise ValidationError("Broker did not provide a current price for OPTION placement")
            price = candles[-1].close
        command = execute_payload(request, account.id, boundary, price)
        supervisor = self._client.require_supervisor()
        async with self._submission_lock:
            if self._submission_uncertain:
                raise OrderSubmissionUnknownError(
                    "A previous order is still awaiting reconciliation; submission is blocked"
                )
            loop = asyncio.get_running_loop()
            self._confirmation = loop.create_future()
            command_started = False
            try:
                command_started = True
                await supervisor.send("/user/topic/execute", command)
                order = await asyncio.wait_for(
                    self._confirmation, timeout=self._client.config.connect_timeout
                )
            except asyncio.CancelledError:
                if command_started:
                    self._submission_uncertain = True
                raise
            except (OrderError, ProtocolError, ValidationError):
                raise
            except Exception as exc:
                self._submission_uncertain = True
                raise OrderSubmissionUnknownError(
                    "Order send outcome is unknown; the command was not replayed"
                ) from exc
            finally:
                self._confirmation = None
        self._trackers.setdefault(order.id, OrderTracker(order))
        return order

    async def list(self, query: OrderQuery | None = None) -> list[Order]:
        if query is None:
            assets = await self._client.market.list_assets()
            query = OrderQuery(
                symbols=tuple(asset.symbol for asset in assets),
                timeframes=tuple(Timeframe),
                statuses=tuple(TERMINAL_STATUSES),
            )
        if query.page < 0 or query.size <= 0:
            raise ValidationError("Order page must be non-negative and size positive")
        params: dict[str, object] = {
            "page": query.page,
            "size": query.size,
        }
        if query.order_type:
            params["binaryOrderTypes"] = query.order_type
        if query.symbols:
            params["symbols"] = ",".join(query.symbols)
        if query.timeframes:
            params["candleTimeFrames"] = ",".join(frame.value for frame in query.timeframes)
        if query.statuses:
            params["statuses"] = ",".join(status.value for status in query.statuses)
        response = await self._client._request("GET", "/orders", params=params)  # noqa: SLF001
        raw = response.json()
        values: object = raw
        if isinstance(raw, dict):
            values = raw.get("content", raw.get("data", raw.get("orders", [])))
        if not isinstance(values, list):
            raise ProtocolError("Order history response is not a list")
        orders = [parse_order(value) for value in values if isinstance(value, dict)]
        for order in orders:
            tracker = self._trackers.get(order.id)
            if tracker is None:
                self._trackers[order.id] = OrderTracker(order)
            else:
                await tracker.update(order)
        return orders

    async def get(self, order_id: str, *, refresh: bool = False) -> Order | None:
        tracker = self._trackers.get(order_id)
        if not refresh and tracker:
            return tracker.order
        assets = await self._client.market.list_assets() if tracker is None else ()
        symbols = (
            (tracker.order.request.symbol,)
            if tracker is not None
            else tuple(asset.symbol for asset in assets)
        )
        for page in range(10):
            query = OrderQuery(
                page=page,
                size=100,
                symbols=symbols,
                timeframes=(tracker.order.request.timeframe,) if tracker else tuple(Timeframe),
                statuses=tuple(OrderStatus),
            )
            orders = await self.list(query)
            if order := next((item for item in orders if item.id == order_id), None):
                return order
            if len(orders) < 100:
                break
        return self._trackers.get(order_id).order if order_id in self._trackers else None

    async def wait(self, order_id: str, timeout: float | None = None) -> Settlement:  # noqa: ASYNC109
        order = await self.get(order_id)
        if order is None:
            raise ValidationError(f"Unknown order: {order_id}")
        tracker = self._trackers[order_id]
        deadline = timeout if timeout is not None else self._client.config.settlement_timeout
        try:
            terminal = await asyncio.wait_for(tracker.wait_terminal(), timeout=deadline)
        except TimeoutError:
            reconciled = await self.get(order_id, refresh=True)
            if reconciled and reconciled.status in TERMINAL_STATUSES:
                terminal = reconciled
            else:
                raise SettlementTimeoutError(
                    "Order settlement remains unknown", last_order=reconciled or tracker.order
                ) from None
        return Settlement(terminal, terminal.profit or Decimal(0))

    async def handle_event(self, destination: str, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        raw: object = payload
        envelope = payload.get("data")
        if isinstance(envelope, dict):
            if envelope.get("event") != "single_user_order":
                return
            raw = envelope.get("payload")
        execute_confirmation = destination == "/user/topic/execute"
        if execute_confirmation and self._submission_uncertain:
            self._submission_uncertain = False
        if not isinstance(raw, dict) or "status" not in raw:
            if execute_confirmation and self._confirmation is not None:
                error: Exception
                if isinstance(raw, dict) and (
                    raw.get("error") or raw.get("success") is False or raw.get("accepted") is False
                ):
                    error = OrderRejectedError("Broker rejected the OPTION order")
                else:
                    error = ProtocolError("Broker execute confirmation is malformed")
                if not self._confirmation.done():
                    self._confirmation.set_exception(error)
            return
        order = parse_order(raw)
        if execute_confirmation and self._confirmation is not None:
            if not self._confirmation.done():
                self._confirmation.set_result(order)
        tracker = self._trackers.get(order.id)
        if tracker is None:
            self._trackers[order.id] = OrderTracker(order)
        else:
            await tracker.update(order)
        self._client.events.emit(OrderEvent(datetime.now(UTC), order))
