"""OPTION order domain models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from ..market.models import Timeframe


class Direction(StrEnum):
    CALL = "CALL"
    PUT = "PUT"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    WIN = "WIN"
    LOSE = "LOSE"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    symbol: str
    direction: Direction
    investment: Decimal
    timeframe: Timeframe
    price: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Order:
    id: str
    request: OrderRequest
    status: OrderStatus
    placed_at: datetime
    opened_at: datetime | None = None
    settled_at: datetime | None = None
    open_price: Decimal | None = None
    close_price: Decimal | None = None
    profit: Decimal | None = None
    fees: Decimal | None = None
    payout: Decimal | None = None
    scheduled_open_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Settlement:
    order: Order
    profit: Decimal


@dataclass(frozen=True, slots=True)
class OrderQuery:
    page: int = 0
    size: int = 50
    symbols: tuple[str, ...] = ()
    timeframes: tuple[Timeframe, ...] = ()
    statuses: tuple[OrderStatus, ...] = ()
    order_type: str | None = None
