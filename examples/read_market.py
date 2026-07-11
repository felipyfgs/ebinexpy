"""Read-only TEST account and market example."""

import asyncio
import os

from ebinexpy import EbinexClient, Timeframe


async def main() -> None:
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        assets = await client.list_assets()
        active = next(
            asset for asset in assets if asset.tradable and Timeframe.M1 in asset.timeframes
        )
        print(active.symbol, await client.get_payout(active.symbol, Timeframe.M1))

        stream = await client.stream_candles(active.symbol, Timeframe.M1)
        async with stream:
            event = await stream.__anext__()
            print(event.candle)


if __name__ == "__main__":
    asyncio.run(main())
