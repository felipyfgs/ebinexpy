from types import SimpleNamespace

import pytest

from ebinexpy.events import EventDispatcher
from ebinexpy.market import Timeframe
from ebinexpy.market.service import MarketService


class FakeSupervisor:
    ready = True

    def __init__(self) -> None:
        self.destinations: list[str] = []
        self.released: list[str] = []

    async def subscribe(self, destination: str) -> str:
        self.destinations.append(destination)
        return f"handle-{len(self.destinations)}"

    async def unsubscribe(self, handle: str) -> None:
        self.released.append(handle)


class FakeClient:
    def __init__(self) -> None:
        self.config = SimpleNamespace(event_queue_size=1, environment=SimpleNamespace(value="TEST"))
        self.accounts = SimpleNamespace(
            selected=SimpleNamespace(environment=SimpleNamespace(value="REAL"))
        )
        self.events = EventDispatcher()
        self.supervisor = FakeSupervisor()

    def require_supervisor(self) -> FakeSupervisor:
        return self.supervisor


@pytest.mark.asyncio
async def test_live_consumers_are_bounded_routed_and_cleaned_up() -> None:
    client = FakeClient()
    service = MarketService(client)  # type: ignore[arg-type]
    first = await service.stream_candles("IDXUSDT", Timeframe.M1)
    second = await service.stream_candles("IDXUSDT", Timeframe.M1)
    other = await service.stream_candles("OTHER", Timeframe.M1)
    trade = {
        "data": {
            "event": "trade",
            "payload": {"t": 1_700_000_000_000, "o": 1, "h": 2, "l": 1, "c": 2, "v": 3},
        }
    }

    await service.handle_event("/topic/graph:IDXUSDT:M1", trade)

    assert (await first.__anext__()).candle.symbol == "IDXUSDT"
    assert (await second.__anext__()).candle.symbol == "IDXUSDT"
    assert other._queue.empty()  # noqa: SLF001
    await first.close()
    await second.close()
    await other.close()
    assert len(client.supervisor.released) == 3


@pytest.mark.asyncio
async def test_snapshots_and_tickers_are_routed_only_to_their_market_key() -> None:
    client = FakeClient()
    service = MarketService(client)  # type: ignore[arg-type]
    first = await service.stream_candles("AAA", Timeframe.M1)
    other = await service.stream_candles("BBB", Timeframe.M5)
    ticker = await service.stream_ticker("AAA", Timeframe.M1)
    other_ticker = await service.stream_ticker("BBB", Timeframe.M1)

    await service.handle_event(
        "/topic/graph:AAA:M1",
        {
            "data": {
                "event": "candles_history",
                "payload": [{"t": 1_700_000_000_000, "o": 1, "h": 2, "l": 1, "c": 2, "v": 3}],
            }
        },
    )
    await service.handle_event(
        "/user/topic/TEST",
        {
            "data": {
                "event": "ticker",
                "payload": {
                    "symbol": "AAA",
                    "candleTimeFrame": "M1",
                    "volume": {"volume24": 10},
                    "book": {"green": 6, "red": 4},
                },
            }
        },
    )

    assert (await anext(first)).candle.symbol == "AAA"
    assert other._queue.empty()  # noqa: SLF001
    assert (await anext(ticker)).ticker.symbol == "AAA"
    assert other_ticker._queue.empty()  # noqa: SLF001
    await first.close()
    await other.close()
    await ticker.close()
    await other_ticker.close()


@pytest.mark.asyncio
async def test_book_subscription_uses_selected_account_environment() -> None:
    client = FakeClient()
    service = MarketService(client)  # type: ignore[arg-type]
    stream = await service.stream_book("IDXUSDT", Timeframe.M1)

    assert client.supervisor.destinations == ["/topic/book:REAL:IDXUSDT:M1"]
    await stream.close()
