import asyncio
from datetime import UTC, datetime

import pytest

from ebinexpy.core.exceptions import EventQueueOverflowError
from ebinexpy.events import ConnectionEvent, ConnectionState, EventDispatcher, EventStream


@pytest.mark.asyncio
async def test_dispatcher_isolates_handler_failure() -> None:
    errors = []
    received = []
    dispatcher = EventDispatcher(lambda error, _handler, _event: errors.append(error))

    async def broken(_event):
        raise RuntimeError("boom")

    async def healthy(event):
        received.append(event)

    dispatcher.add(broken)
    dispatcher.add(healthy)
    event = ConnectionEvent(datetime.now(UTC), ConnectionState.CONNECTED)
    dispatcher.emit(event)
    await dispatcher.close()

    assert received == [event]
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_market_stream_coalesces_and_lossless_stream_overflows() -> None:
    market = EventStream[int](1, coalesce=True)
    market.publish(1)
    market.publish(2)
    assert await anext(market) == 2
    await market.close()

    lifecycle = EventStream[int](1)
    lifecycle.publish(1)
    lifecycle.publish(2)
    with pytest.raises(EventQueueOverflowError):
        await anext(lifecycle)


@pytest.mark.asyncio
async def test_cancelled_stream_wait_releases_resources() -> None:
    cleaned = asyncio.Event()
    stream = EventStream[int](1, cleanup=cleaned.set)
    consumer = asyncio.create_task(anext(stream))

    await asyncio.sleep(0)
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer

    assert cleaned.is_set()
