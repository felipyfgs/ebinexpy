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
