"""Private order wire shapes and parsers."""

from datetime import UTC, datetime
from typing import Any

from ..core.exceptions import ProtocolError
from ..core.money import as_decimal
from ..market.models import Timeframe
from ..market.wire import timestamp
from .models import Direction, Order, OrderRequest, OrderStatus

TERMINAL_STATUSES = {
    OrderStatus.WIN,
    OrderStatus.LOSE,
    OrderStatus.REFUNDED,
    OrderStatus.CANCELED,
}


def optional_time(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
    return timestamp(value)


def optional_decimal(value: object) -> Any:
    return None if value is None else as_decimal(value)


def parse_order(value: dict[str, Any]) -> Order:
    try:
        status = OrderStatus(str(value["status"]).upper())
        wire_direction = str(value["direction"]).upper()
        if wire_direction == "BULL":
            direction = Direction.CALL
        elif wire_direction == "BEAR":
            direction = Direction.PUT
        else:
            raise ProtocolError(f"Unknown broker order direction: {wire_direction}")
        order_id = str(value.get("id") or "").strip()
        if not order_id:
            raise ProtocolError("Order broker ID is missing")
        request = OrderRequest(
            symbol=str(value["symbol"]),
            direction=direction,
            investment=as_decimal(value["invest"]),
            timeframe=Timeframe(str(value["candleTimeFrame"]).upper()),
            price=optional_decimal(value.get("price")),
        )
        placed_at = optional_time(value.get("createdAt") or value.get("createdAtBrokerTime"))
        if placed_at is None:
            raise ProtocolError("Order creation timestamp is missing")
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError("Order payload is malformed") from exc
    scheduled = optional_time(value.get("candleStartTime"))
    expires = optional_time(value.get("candleEndTime"))
    return Order(
        id=order_id,
        request=request,
        status=status,
        placed_at=placed_at,
        opened_at=scheduled if status is not OrderStatus.PENDING else None,
        settled_at=expires if status in TERMINAL_STATUSES else None,
        open_price=optional_decimal(value.get("cop")),
        close_price=optional_decimal(value.get("ccp")),
        profit=optional_decimal(value.get("profit")),
        fees=optional_decimal(value.get("fees")),
        payout=optional_decimal(
            (value.get("payoutComposition") or {}).get("finalPayout")
            if isinstance(value.get("payoutComposition"), dict)
            else None
        ),
        scheduled_open_at=scheduled,
        expires_at=expires,
    )


def execute_payload(
    request: OrderRequest,
    account_id: str,
    boundary_ms: int,
    price: object,
) -> dict[str, object]:
    return {
        "binaryOrderType": "OPTION",
        "accountId": account_id,
        "candleTimeFrame": request.timeframe.value,
        "candleEndTime": boundary_ms,
        "symbol": request.symbol.upper(),
        "direction": "BULL" if request.direction is Direction.CALL else "BEAR",
        "invest": format(request.investment, "f"),
        "asset": "USDT",
        "price": as_decimal(price),
    }
