"""One explicitly gated minimum-stake TEST OPTION order."""

import asyncio
import os
from decimal import Decimal

from ebinexpy import Direction, EbinexClient, OrderRequest, Timeframe


async def main() -> None:
    if os.environ.get("EBINEXPY_ALLOW_DEMO_ORDER") != "YES_ONE_DEMO_ORDER":
        raise SystemExit("Set EBINEXPY_ALLOW_DEMO_ORDER=YES_ONE_DEMO_ORDER deliberately")
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        symbol = "IDXUSDT"
        stream = await client.stream_candles(symbol, Timeframe.M1)
        async with stream:
            price = (await stream.__anext__()).candle.close
        order = await client.place_order(
            OrderRequest(symbol, Direction.CALL, Decimal("1"), Timeframe.M1, price)
        )
        print(await client.wait_order(order.id))


if __name__ == "__main__":
    asyncio.run(main())
