"""Market-data domain models."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"


class MarketStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True, slots=True)
class Asset:
    symbol: str
    label: str
    status: MarketStatus
    payout: Decimal
    timeframes: tuple[Timeframe, ...]
    display_order: int = 0

    @property
    def tradable(self) -> bool:
        return self.status is MarketStatus.ACTIVE and bool(self.timeframes)


@dataclass(frozen=True, slots=True)
class Candle:
    symbol: str
    timeframe: Timeframe
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class Ticker:
    symbol: str
    timeframe: Timeframe
    volume_24h: Decimal
    bull_total: Decimal
    bear_total: Decimal


@dataclass(frozen=True, slots=True)
class BookUpdate:
    symbol: str
    timeframe: Timeframe
    direction: str
    investment: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BrokerTime:
    value: datetime
    received_at: datetime

    @property
    def age_seconds(self) -> float:
        return max(0.0, (datetime.now(self.received_at.tzinfo) - self.received_at).total_seconds())
