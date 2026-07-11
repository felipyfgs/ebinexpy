import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from ebinexpy.accounts import Account, AccountEnvironment
from ebinexpy.core import (
    OrderRejectedError,
    OrderSubmissionUnknownError,
    ProtocolError,
    RealTradingDisabledError,
    SettlementTimeoutError,
    ValidationError,
)
from ebinexpy.events import EventDispatcher
from ebinexpy.market import Asset, MarketStatus, Timeframe
from ebinexpy.orders import Direction, OrderRequest, OrderStatus
from ebinexpy.orders.service import OrderService
from ebinexpy.orders.state import OrderTracker
from ebinexpy.orders.validation import guard_environment, validate_request
from ebinexpy.orders.wire import execute_payload, parse_order


def lifecycle() -> list[dict[str, object]]:
    wrapped = json.loads(Path("tests/fixtures/ws/order_lifecycle.json").read_text())
    return [item["data"]["payload"] for item in wrapped]


def test_captured_order_lifecycle_and_decimal_fields() -> None:
    pending, opened, settled = (parse_order(value) for value in lifecycle())
    assert pending.status is OrderStatus.PENDING
    assert pending.opened_at is None
    assert opened.status is OrderStatus.OPEN
    assert settled.status is OrderStatus.WIN
    assert settled.profit == Decimal("0.96")
    assert settled.open_price == Decimal("2995.56")


@pytest.mark.asyncio
async def test_tracker_rejects_terminal_mutation() -> None:
    pending, _, settled = (parse_order(value) for value in lifecycle())
    tracker = OrderTracker(pending)
    await tracker.update(settled)
    changed = {**lifecycle()[-1], "status": "LOSE"}
    with pytest.raises(ProtocolError):
        await tracker.update(parse_order(changed))


@pytest.mark.parametrize("status", ["WIN", "LOSE", "REFUNDED", "CANCELED"])
@pytest.mark.asyncio
async def test_tracker_accepts_every_broker_terminal_status(status: str) -> None:
    pending = parse_order(lifecycle()[0])
    terminal = parse_order({**lifecycle()[-1], "status": status})
    tracker = OrderTracker(pending)
    await tracker.update(terminal)
    assert tracker.order.status.value == status


def test_validation_and_real_guard_happen_without_network() -> None:
    asset = Asset("IDXUSDT", "IDX", MarketStatus.ACTIVE, Decimal("96"), (Timeframe.M1,))
    with pytest.raises(ValidationError):
        validate_request(OrderRequest("IDXUSDT", Direction.CALL, Decimal("0"), Timeframe.M1), asset)
    closed = Asset("IDXUSDT", "IDX", MarketStatus.INACTIVE, Decimal("96"), (Timeframe.M1,))
    with pytest.raises(ValidationError):
        validate_request(
            OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M1), closed
        )
    with pytest.raises(ValidationError):
        validate_request(OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M5), asset)
    with pytest.raises(RealTradingDisabledError):
        guard_environment(AccountEnvironment.REAL, False)


def test_execute_payload_maps_direction_and_decimal() -> None:
    request = OrderRequest(
        "IDXUSDT", Direction.PUT, Decimal("1.25"), Timeframe.M1, Decimal("2998.92")
    )
    payload = execute_payload(request, "test-account", 120_000, request.price)
    assert payload["direction"] == "BEAR"
    assert payload["invest"] == "1.25"
    assert payload["binaryOrderType"] == "OPTION"


@dataclass
class DummyConfig:
    allow_real_trading: bool = False
    connect_timeout: float = 0.2
    settlement_timeout: float = 0.01


class DummyMarket:
    def __init__(self, asset: Asset) -> None:
        self.asset = asset

    async def get_asset(self, _symbol: str, *, refresh: bool = False) -> Asset:
        return self.asset

    async def list_assets(self) -> list[Asset]:
        return [self.asset]

    def get_broker_time(self) -> None:
        return None


class DummySupervisor:
    def __init__(self) -> None:
        self.service: OrderService | None = None
        self.index = 0

    async def send(self, destination: str, body: object) -> None:
        self.index += 1
        raw = {**lifecycle()[0], "id": f"order-{self.index}"}
        await asyncio.sleep(0)
        assert self.service is not None
        await self.service.handle_event(destination, raw)


class DummyClient:
    def __init__(self) -> None:
        asset = Asset("IDXUSDT", "IDX", MarketStatus.ACTIVE, Decimal("96"), (Timeframe.M1,))
        self.config = DummyConfig()
        self.accounts = type(
            "Accounts", (), {"selected": Account("test", AccountEnvironment.TEST)}
        )()
        self.market = DummyMarket(asset)
        self.events = EventDispatcher()
        self.supervisor = DummySupervisor()
        self.requests: list[dict[str, object]] = []

    def require_supervisor(self) -> DummySupervisor:
        return self.supervisor

    async def _request(self, *_args: object, **_kwargs: object) -> httpx.Response:
        self.requests.append(_kwargs["params"])  # type: ignore[arg-type]
        return httpx.Response(200, json=[])


@pytest.mark.asyncio
async def test_concurrent_submissions_keep_confirmations_correlated() -> None:
    client = DummyClient()
    service = OrderService(client)  # type: ignore[arg-type]
    client.supervisor.service = service
    requests = [
        OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M1, Decimal("10")),
        OrderRequest("IDXUSDT", Direction.PUT, Decimal("2"), Timeframe.M1, Decimal("10")),
    ]

    orders = await asyncio.gather(*(service.place(request) for request in requests))

    assert [order.id for order in orders] == ["order-1", "order-2"]


@pytest.mark.asyncio
async def test_unknown_settlement_raises_with_last_order_never_lose() -> None:
    client = DummyClient()
    service = OrderService(client)  # type: ignore[arg-type]
    pending = parse_order(lifecycle()[0])
    service._trackers[pending.id] = OrderTracker(pending)  # noqa: SLF001

    with pytest.raises(SettlementTimeoutError) as captured:
        await service.wait(pending.id, timeout=0.001)

    assert captured.value.last_order.status is OrderStatus.PENDING


@pytest.mark.asyncio
async def test_broker_rejection_is_typed_and_not_wrapped_as_unknown() -> None:
    client = DummyClient()
    service = OrderService(client)  # type: ignore[arg-type]
    client.supervisor.service = service

    async def reject(destination: str, _body: object) -> None:
        await service.handle_event(destination, {"success": False, "error": "redacted"})

    client.supervisor.send = reject  # type: ignore[method-assign]
    request = OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M1, Decimal("10"))
    with pytest.raises(OrderRejectedError):
        await service.place(request)


@pytest.mark.asyncio
async def test_ambiguous_send_failure_is_unknown_and_never_replayed() -> None:
    client = DummyClient()
    service = OrderService(client)  # type: ignore[arg-type]
    sends = 0

    async def fail(_destination: str, _body: object) -> None:
        nonlocal sends
        sends += 1
        raise OSError("socket lost")

    client.supervisor.send = fail  # type: ignore[method-assign]
    request = OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M1, Decimal("10"))
    with pytest.raises(OrderSubmissionUnknownError):
        await service.place(request)
    assert sends == 1


@pytest.mark.asyncio
async def test_late_confirmation_cannot_satisfy_the_next_submission() -> None:
    client = DummyClient()
    client.config.connect_timeout = 0.001
    service = OrderService(client)  # type: ignore[arg-type]
    sends = 0

    async def no_confirmation(_destination: str, _body: object) -> None:
        nonlocal sends
        sends += 1

    client.supervisor.send = no_confirmation  # type: ignore[method-assign]
    request = OrderRequest("IDXUSDT", Direction.CALL, Decimal("1"), Timeframe.M1, Decimal("10"))
    with pytest.raises(OrderSubmissionUnknownError):
        await service.place(request)
    with pytest.raises(OrderSubmissionUnknownError, match="reconciliation"):
        await service.place(request)
    assert sends == 1

    late = {**lifecycle()[0], "id": "late-order"}
    await service.handle_event("/user/topic/execute", late)

    async def confirm(destination: str, _body: object) -> None:
        nonlocal sends
        sends += 1
        current = {**lifecycle()[0], "id": "current-order"}
        await service.handle_event(destination, current)

    client.supervisor.send = confirm  # type: ignore[method-assign]
    order = await service.place(request)
    assert order.id == "current-order"
    assert sends == 2


@pytest.mark.asyncio
async def test_unknown_order_lookup_includes_active_statuses_and_uses_full_pages() -> None:
    client = DummyClient()
    service = OrderService(client)  # type: ignore[arg-type]
    target = {**lifecycle()[0], "id": "active-order"}

    async def respond(*_args: object, **kwargs: object) -> httpx.Response:
        client.requests.append(kwargs["params"])  # type: ignore[arg-type]
        return httpx.Response(200, json=[target])

    client._request = respond  # type: ignore[method-assign]
    order = await service.get("active-order", refresh=True)

    assert order is not None
    assert order.status is OrderStatus.PENDING
    assert client.requests[0]["size"] == 100
    assert "PENDING" in str(client.requests[0]["statuses"])
    assert "OPEN" in str(client.requests[0]["statuses"])


@pytest.mark.asyncio
async def test_terminal_reconciliation_enriches_financial_fields() -> None:
    partial_payload = {
        key: value for key, value in lifecycle()[-1].items() if key not in {"profit", "fees", "ccp"}
    }
    tracker = OrderTracker(parse_order(partial_payload))
    await tracker.update(parse_order(lifecycle()[-1]))

    assert tracker.order.profit == Decimal("0.96")
    assert tracker.order.fees == Decimal("0.04")
    assert tracker.order.close_price == Decimal("2995.83")


@pytest.mark.parametrize(
    "changes",
    [
        {"direction": "SIDEWAYS"},
        {"id": ""},
    ],
)
def test_order_parser_rejects_unknown_direction_and_missing_id(changes: dict[str, str]) -> None:
    with pytest.raises(ProtocolError):
        parse_order({**lifecycle()[0], **changes})
