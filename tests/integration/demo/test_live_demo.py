"""Opt-in live TEST acceptance. Never enabled by CI."""

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ebinexpy import (
    AccountEnvironment,
    BrokerTimeEvent,
    ClientConfig,
    Direction,
    EbinexClient,
    OrderEvent,
    OrderRequest,
    OrderStatus,
    Timeframe,
)

LIVE = os.environ.get("EBINEXPY_RUN_LIVE") == "1"
ORDER = os.environ.get("EBINEXPY_RUN_DEMO_ORDER") == "YES_ONE_DEMO_ORDER"
CREDS = bool(os.environ.get("EBINEX_EMAIL") and os.environ.get("EBINEX_PASSWORD"))

pytestmark = pytest.mark.skipif(not (LIVE and CREDS), reason="live DEMO acceptance is opt-in")


@pytest.mark.asyncio
async def test_live_demo_read_only_surface() -> None:
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        assert client.accounts.selected is not None
        assert client.accounts.selected.environment is AccountEnvironment.TEST
        assert await client.list_accounts()
        assert await client.get_profile()
        assets = await client.list_assets(refresh=True)
        asset = next(item for item in assets if item.tradable and Timeframe.M1 in item.timeframes)
        assert await client.get_payout(asset.symbol, Timeframe.M1) > 0
        assert isinstance(await client.list_orders(), list)
        broker_time_received = asyncio.Event()

        def observe_broker_time(event: object) -> None:
            if isinstance(event, BrokerTimeEvent):
                broker_time_received.set()

        client.events.add(observe_broker_time)

        now = datetime.now(UTC)
        candles = await client.get_candles(
            asset.symbol, Timeframe.M1, now - timedelta(minutes=10), now
        )
        assert candles == sorted(candles, key=lambda candle: candle.open_time)

        ticker_stream = await client.stream_ticker(asset.symbol, Timeframe.M1)
        book_stream = await client.stream_book(asset.symbol, Timeframe.M1)
        candles_stream = await client.stream_candles(asset.symbol, Timeframe.M1)
        async with candles_stream, ticker_stream, book_stream, asyncio.timeout(20):
            candle_event, ticker_event, book_event = await asyncio.gather(
                candles_stream.__anext__(), ticker_stream.__anext__(), book_stream.__anext__()
            )
            assert candle_event.candle.symbol == asset.symbol
            assert ticker_event.ticker.symbol == asset.symbol
            assert book_event.update.symbol == asset.symbol
            await broker_time_received.wait()
            assert client.get_broker_time() is not None


@pytest.mark.asyncio
async def test_live_demo_remaining_lifecycle_balance_and_raw_surface() -> None:
    client = EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"])
    await client.connect()
    try:
        await client.wait_until_ready(timeout=10)
        selected = await client.select_account(AccountEnvironment.TEST)
        assert selected.environment is AccountEnvironment.TEST
        assert (await client.get_balance()).amount >= 0

        asset = await client.get_asset("IDXUSDT", refresh=True)
        assert await client.is_market_open(asset.symbol, Timeframe.M1)

        parameters = await client.raw.request("GET", "/parameters")
        assert parameters.status_code == 200

        raw_stream = await client.raw.subscribe(f"/topic/graph:{asset.symbol}:M1")
        async with raw_stream, asyncio.timeout(20):
            frame = await raw_stream.__anext__()
            assert frame.headers["destination"] == f"/topic/graph:{asset.symbol}:M1"

        await client.disconnect()
        await client.disconnect()
        assert not client.connected
        await client.connect()
        await client.wait_until_ready(timeout=10)
        assert client.connected
    finally:
        await client.logout()
    assert not client.authenticated


@pytest.mark.asyncio
async def test_live_demo_reauthentication_and_file_session_restore(tmp_path) -> None:
    email = os.environ["EBINEX_EMAIL"]
    password = os.environ["EBINEX_PASSWORD"]
    config = ClientConfig.with_file_sessions(tmp_path / "sessions")
    first = EbinexClient(email, password, config)
    await first.connect()
    assert first.auth.session is not None
    first.auth.session = replace(first.auth.session, access_token="invalid-live-test-token")
    assert (await first.get_profile()).id
    assert first.auth.session is not None
    assert first.auth.session.access_token != "invalid-live-test-token"
    await first.close()

    second = EbinexClient(email, password, config)
    await second.connect()
    assert second.connected
    await second.logout()
    assert await config.session_store.load(email) is None


@pytest.mark.skipif(not ORDER, reason="requires explicit authorization for exactly one TEST order")
@pytest.mark.asyncio
async def test_live_demo_exactly_one_settlement() -> None:
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        assert client.accounts.selected is not None
        assert client.accounts.selected.environment is AccountEnvironment.TEST
        before = (await client.get_balance()).amount
        asset = await client.get_asset("IDXUSDT", refresh=True)
        assert asset.tradable and Timeframe.M1 in asset.timeframes
        statuses: list[OrderStatus] = []

        def observe_order(event: object) -> None:
            if isinstance(event, OrderEvent):
                statuses.append(event.order.status)

        client.events.add(observe_order)
        stream = await client.stream_candles(asset.symbol, Timeframe.M1)
        async with stream, asyncio.timeout(20):
            price = (await stream.__anext__()).candle.close

        order = await client.place_order(
            OrderRequest(asset.symbol, Direction.CALL, Decimal("1"), Timeframe.M1, price)
        )
        assert order.status is OrderStatus.PENDING
        assert (await client.get_order(order.id)) == order
        settlement = await client.wait_order(order.id, timeout=180)
        assert settlement.order.status in {
            OrderStatus.WIN,
            OrderStatus.LOSE,
            OrderStatus.REFUNDED,
            OrderStatus.CANCELED,
        }
        await asyncio.sleep(0)
        assert OrderStatus.PENDING in statuses
        assert OrderStatus.OPEN in statuses
        assert settlement.order.status in statuses
        reconciled = await client.get_order(order.id, refresh=True)
        assert reconciled is not None
        assert reconciled.status is settlement.order.status
        after = next(
            account.balance
            for account in await client.list_accounts()
            if account.environment is AccountEnvironment.TEST
        )
        assert after != before or settlement.order.status in {
            OrderStatus.REFUNDED,
            OrderStatus.CANCELED,
        }
