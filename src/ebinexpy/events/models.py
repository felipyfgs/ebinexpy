"""Shared event models."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..accounts.models import Balance
from ..market.models import BookUpdate, Candle, Ticker
from ..orders.models import Order


@dataclass(frozen=True, slots=True)
class Event:
    occurred_at: datetime


class ConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"


@dataclass(frozen=True, slots=True)
class ConnectionEvent(Event):
    state: ConnectionState
    attempt: int = 0


@dataclass(frozen=True, slots=True)
class BalanceEvent(Event):
    balance: Balance


@dataclass(frozen=True, slots=True)
class BrokerTimeEvent(Event):
    broker_time: datetime


@dataclass(frozen=True, slots=True)
class CandleEvent(Event):
    candle: Candle
    snapshot: bool = False


@dataclass(frozen=True, slots=True)
class TickerEvent(Event):
    ticker: Ticker


@dataclass(frozen=True, slots=True)
class BookEvent(Event):
    update: BookUpdate
    snapshot: bool = False


@dataclass(frozen=True, slots=True)
class OrderEvent(Event):
    order: Order
