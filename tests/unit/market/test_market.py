import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from ebinexpy.core import ProtocolError
from ebinexpy.market import MarketStatus, Timeframe
from ebinexpy.market.service import MarketService
from ebinexpy.market.wire import parse_asset, parse_candle


def test_option_assets_preserve_status_payout_order_and_frames() -> None:
    values = json.loads(Path("tests/fixtures/rest/available_symbols.json").read_text())
    active, closed = (parse_asset(value) for value in values)

    assert active.status is MarketStatus.ACTIVE
    assert active.payout == Decimal("96")
    assert active.display_order == 1
    assert active.timeframes == (Timeframe.M1, Timeframe.M5, Timeframe.M15)
    assert closed.tradable is False


def test_malformed_candle_is_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_candle({"t": 1, "o": 1}, "IDXUSDT", Timeframe.M1)
    with pytest.raises(ProtocolError):
        parse_candle(
            {"t": 1, "o": 10, "h": 9, "l": 8, "c": 10, "v": 1},
            "IDXUSDT",
            Timeframe.M1,
        )


class FakeClient:
    def __init__(self, pages: list[list[dict[str, object]]]) -> None:
        self.pages = pages
        self.calls: list[dict[str, object]] = []

    async def _request(self, _method: str, _path: str, **kwargs: object) -> httpx.Response:
        self.calls.append(kwargs["params"])  # type: ignore[arg-type]
        return httpx.Response(200, json=self.pages.pop(0))


@pytest.mark.asyncio
async def test_history_paginates_deduplicates_and_sorts() -> None:
    base = 1_700_000_000_000
    first = [
        {"t": base + 60_000, "o": 1, "h": 2, "l": 1, "c": 2, "v": 3},
        {"t": base + 120_000, "o": 2, "h": 3, "l": 2, "c": 3, "v": 4},
    ]
    second = [
        {"t": base + 120_000, "o": 2, "h": 3, "l": 2, "c": 3, "v": 4},
        {"t": base + 180_000, "o": 3, "h": 4, "l": 3, "c": 4, "v": 5},
    ]
    client = FakeClient([first, second, []])
    service = MarketService(client)  # type: ignore[arg-type]
    candles = await service.get_candles(
        "IDXUSDT",
        Timeframe.M1,
        datetime.fromtimestamp(base / 1000, UTC),
        datetime.fromtimestamp((base + 300_000) / 1000, UTC),
        limit=2,
    )

    assert [int(candle.open_time.timestamp() * 1000) for candle in candles] == [
        base + 60_000,
        base + 120_000,
        base + 180_000,
    ]
    assert client.calls[1]["from"] == base + 180_000
