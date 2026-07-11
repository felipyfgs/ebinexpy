"""Private market-data wire shapes and parsers."""

from datetime import UTC, datetime
from typing import Any

from ..core.exceptions import ProtocolError
from ..core.money import as_decimal
from .models import Asset, BookUpdate, Candle, MarketStatus, Ticker, Timeframe


def timestamp(value: object) -> datetime:
    try:
        numeric = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Broker timestamp is invalid") from exc
    if numeric > 10_000_000_000:
        numeric /= 1000
    return datetime.fromtimestamp(numeric, UTC)


def parse_asset(value: dict[str, Any]) -> Asset:
    option = value.get("configModes", {}).get("OPTION", {})
    if not isinstance(option, dict):
        option = {}
    frames: list[Timeframe] = []
    for raw in option.get("candleTimeFrames", []):
        try:
            frames.append(Timeframe(str(raw).upper()))
        except ValueError:
            continue
    status_value = str(option.get("status", value.get("marketStatus", "INACTIVE"))).upper()
    status = MarketStatus.ACTIVE if status_value == "ACTIVE" else MarketStatus.INACTIVE
    return Asset(
        symbol=str(value.get("symbol") or ""),
        label=str(value.get("symbolLabel") or value.get("label") or value.get("symbol") or ""),
        status=status,
        payout=as_decimal(option.get("payout", value.get("payout", 0))),
        timeframes=tuple(frames),
        display_order=int(option.get("displayOrder") or 0),
    )


def parse_candle(value: dict[str, Any], symbol: str, timeframe: Timeframe) -> Candle:
    required = ("t", "o", "h", "l", "c", "v")
    if any(key not in value or value[key] is None for key in required):
        raise ProtocolError("Candle payload is incomplete")
    candle = Candle(
        symbol=symbol,
        timeframe=timeframe,
        open_time=timestamp(value["t"]),
        open=as_decimal(value["o"]),
        high=as_decimal(value["h"]),
        low=as_decimal(value["l"]),
        close=as_decimal(value["c"]),
        volume=as_decimal(value["v"]),
    )
    if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close):
        raise ProtocolError("Candle OHLC range is inconsistent")
    return candle


def parse_ticker(value: dict[str, Any], symbol: str, timeframe: Timeframe | None = None) -> Ticker:
    volume = value.get("volume", {})
    book = value.get("book", {})
    return Ticker(
        symbol=symbol,
        timeframe=timeframe or Timeframe(str(value["candleTimeFrame"]).upper()),
        volume_24h=as_decimal(volume.get("volume24", 0)),
        bull_total=as_decimal(book.get("green", 0)),
        bear_total=as_decimal(book.get("red", 0)),
    )


def parse_book_order(value: dict[str, Any], symbol: str, timeframe: Timeframe) -> BookUpdate:
    return BookUpdate(
        symbol=symbol,
        timeframe=timeframe,
        direction=str(value.get("direction") or "").upper(),
        investment=as_decimal(value.get("invest", 0)),
        created_at=timestamp(value.get("createdAt", 0)),
    )
