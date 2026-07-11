"""Market-data feature service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from ..core.exceptions import ProtocolError, ValidationError
from ..events.models import BookEvent, BrokerTimeEvent, CandleEvent, TickerEvent
from ..events.streams import EventStream
from .candles import TIMEFRAME_MILLISECONDS, milliseconds
from .models import Asset, BookUpdate, BrokerTime, Candle, MarketStatus, Timeframe
from .wire import parse_asset, parse_book_order, parse_candle, parse_ticker, timestamp

if TYPE_CHECKING:
    from ..client import EbinexClient


class MarketService:
    """Coordinates asset discovery, history and live market streams."""

    def __init__(self, client: EbinexClient) -> None:
        self._client = client
        self._assets: dict[str, Asset] = {}
        self._broker_time: BrokerTime | None = None
        self._candle_streams: dict[tuple[str, Timeframe], set[EventStream[CandleEvent]]] = {}
        self._ticker_streams: dict[tuple[str, Timeframe], set[EventStream[TickerEvent]]] = {}
        self._book_streams: dict[tuple[str, Timeframe], set[EventStream[BookEvent]]] = {}

    async def list_assets(self, *, refresh: bool = False) -> list[Asset]:
        if refresh or not self._assets:
            response = await self._client._request("GET", "/orders/availableSymbols")  # noqa: SLF001
            raw = response.json()
            values = raw.get("data", raw) if isinstance(raw, dict) else raw
            if not isinstance(values, list):
                raise ProtocolError("availableSymbols response is not a list")
            assets = [parse_asset(value) for value in values if isinstance(value, dict)]
            self._assets = {asset.symbol: asset for asset in assets if asset.symbol}
        return sorted(self._assets.values(), key=lambda asset: (asset.display_order, asset.symbol))

    async def get_asset(self, symbol: str, *, refresh: bool = False) -> Asset:
        await self.list_assets(refresh=refresh)
        try:
            return self._assets[symbol.upper()]
        except KeyError as exc:
            raise ValidationError(f"Unknown OPTION symbol: {symbol}") from exc

    async def get_payout(self, symbol: str, timeframe: Timeframe) -> Decimal:
        asset = await self.get_asset(symbol, refresh=True)
        if timeframe not in asset.timeframes:
            raise ValidationError(f"{symbol} does not support {timeframe}")
        return asset.payout

    async def is_market_open(self, symbol: str, timeframe: Timeframe) -> bool:
        asset = await self.get_asset(symbol, refresh=True)
        return asset.status is MarketStatus.ACTIVE and timeframe in asset.timeframes

    def get_broker_time(self) -> BrokerTime | None:
        return self._broker_time

    async def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
        *,
        limit: int = 500,
    ) -> list[Candle]:
        if limit <= 0:
            raise ValidationError("limit must be positive")
        cursor, end_ms = milliseconds(start), milliseconds(end)
        if cursor > end_ms:
            raise ValidationError("start must not be after end")
        candles: dict[datetime, Candle] = {}
        while cursor <= end_ms:
            response = await self._client._request(  # noqa: SLF001
                "GET",
                "/dataProvider/aggregatedTrades",
                params={
                    "symbol": symbol.upper(),
                    "candleTimeFrame": timeframe.value,
                    "from": cursor,
                    "to": end_ms,
                    "limit": limit,
                },
            )
            raw = response.json()
            values = raw.get("data", raw) if isinstance(raw, dict) else raw
            if not isinstance(values, list) or not values:
                break
            page = [parse_candle(value, symbol.upper(), timeframe) for value in values]
            for candle in page:
                candles[candle.open_time] = candle
            newest = max(milliseconds(candle.open_time) for candle in page)
            next_cursor = newest + TIMEFRAME_MILLISECONDS[timeframe]
            if next_cursor <= cursor:
                raise ProtocolError("Candle pagination did not advance")
            cursor = next_cursor
            if len(values) < limit:
                break
        return [candles[key] for key in sorted(candles)]

    async def _stream(
        self,
        registry: dict[tuple[str, Timeframe], set[Any]],
        key: tuple[str, Timeframe],
        destination: str | None,
    ) -> EventStream[Any]:
        supervisor = self._client.require_supervisor()
        handle = await supervisor.subscribe(destination) if destination else None
        stream: EventStream[Any]

        async def cleanup() -> None:
            registry.get(key, set()).discard(stream)
            if not registry.get(key):
                registry.pop(key, None)
            if handle:
                await supervisor.unsubscribe(handle)

        stream = EventStream(self._client.config.event_queue_size, coalesce=True, cleanup=cleanup)
        registry.setdefault(key, set()).add(stream)
        return stream

    async def stream_candles(self, symbol: str, timeframe: Timeframe) -> EventStream[CandleEvent]:
        key = (symbol.upper(), timeframe)
        destination = f"/topic/graph:{key[0]}:{timeframe.value}"
        return await self._stream(self._candle_streams, key, destination)

    async def stream_ticker(self, symbol: str, timeframe: Timeframe) -> EventStream[TickerEvent]:
        key = (symbol.upper(), timeframe)
        return await self._stream(self._ticker_streams, key, None)

    async def stream_book(self, symbol: str, timeframe: Timeframe) -> EventStream[BookEvent]:
        key = (symbol.upper(), timeframe)
        environment = self._client.config.environment.value
        destination = f"/topic/book:{environment}:{key[0]}:{timeframe.value}"
        return await self._stream(self._book_streams, key, destination)

    async def handle_event(self, destination: str, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        envelope = payload.get("data", payload)
        if not isinstance(envelope, dict):
            return
        event = str(envelope.get("event") or "").lower()
        value = envelope.get("payload")
        now = datetime.now(UTC)
        if event == "broker_server_time" and isinstance(value, dict):
            broker_time = timestamp(value.get("serverNowDate"))
            self._broker_time = BrokerTime(broker_time, now)
            self._client.events.emit(BrokerTimeEvent(now, broker_time))
        elif event in {"candles_history", "trade"}:
            values = value if isinstance(value, list) else [value]
            for key, streams in tuple(self._candle_streams.items()):
                if event == "trade" and not self._destination_matches(destination, "graph", key):
                    continue
                for raw in values:
                    if not isinstance(raw, dict):
                        continue
                    item = CandleEvent(now, parse_candle(raw, *key), event == "candles_history")
                    for stream in tuple(streams):
                        stream.publish(item)
                    self._client.events.emit(item)
        elif event == "ticker" and isinstance(value, dict):
            timeframe = Timeframe(str(value.get("candleTimeFrame", "M1")).upper())
            for (symbol, frame), streams in tuple(self._ticker_streams.items()):
                if frame is not timeframe:
                    continue
                item = TickerEvent(now, parse_ticker(value, symbol))
                for stream in tuple(streams):
                    stream.publish(item)
                self._client.events.emit(item)
        elif event in {"book", "book_order"} and isinstance(value, dict):
            await self._handle_book(now, value, event == "book", destination)

    @staticmethod
    def _destination_matches(destination: str, kind: str, key: tuple[str, Timeframe]) -> bool:
        parts = destination.split(":")
        minimum = 3 if kind == "graph" else 4
        return len(parts) >= minimum and parts[-2:] == [key[0], key[1].value]

    async def _handle_book(
        self, now: datetime, value: dict[str, Any], snapshot: bool, destination: str
    ) -> None:
        symbol = str(value.get("symbol") or "").upper()
        frame_raw = value.get("candleTimeFrame")
        matching = [
            (key, streams)
            for key, streams in self._book_streams.items()
            if (not symbol or key[0] == symbol)
            and (not frame_raw or key[1].value == frame_raw)
            and (snapshot or self._destination_matches(destination, "book", key))
        ]
        for key, streams in matching:
            rows: list[dict[str, Any]] = []
            if snapshot:
                for side in ("bull", "bear"):
                    rows.extend(row for row in value.get(side, []) if isinstance(row, dict))
            else:
                rows = [value]
            for row in rows:
                update: BookUpdate = parse_book_order(row, *key)
                item = BookEvent(now, update, snapshot)
                for stream in tuple(streams):
                    stream.publish(item)
                self._client.events.emit(item)
