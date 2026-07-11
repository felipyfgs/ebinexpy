# ebinexpy

`ebinexpy` is an asynchronous Python library for controlling the operational
capabilities of the Ebinex trading room from bots, workers, and other services.
It is not an HTTP API, does not execute strategies, and does not depend on a
browser at runtime.

The current contract is pre-alpha and supports accounts, profiles, balances,
live and historical market data, and the `OPTION` order lifecycle. The `TEST`
account is always the default, and orders on a `REAL` account are blocked
without explicit opt-in.

## Installation

```bash
pip install ebinexpy
```

For development:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Client lifecycle

```python
import asyncio
import os

from ebinexpy import EbinexClient


async def main() -> None:
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        balance = await client.get_balance()
        assets = await client.list_assets()
        print(balance.amount, [asset.symbol for asset in assets if asset.tradable])


asyncio.run(main())
```

The constructor does not open connections. `connect()` authenticates, selects
`TEST`, subscribes to essential topics, and only then marks the client as ready.
`disconnect()` is idempotent and preserves the session; `logout()` disconnects
and removes only the current identity's session. The context manager closes the
HTTP and WebSocket connections and event handlers.

## Sessions

The default is `MemorySessionStore`. To restore sessions across processes, use
a private file:

```python
from pathlib import Path
from ebinexpy import ClientConfig, EbinexClient

config = ClientConfig.with_file_sessions(Path.home() / ".local/state/ebinexpy")
client = EbinexClient("email", "password", config)
```

The store uses an identity-derived key, a `0700` directory, a `0600` file, and
atomic replacement. The library does not read `.env`; load secrets into the
process with your service's configuration tool.

## Market data and streams

Assets and payouts always come from `configModes.OPTION`; the library does not
maintain a static list of tradable assets. Candle dates must be timezone-aware.

```python
from ebinexpy import Timeframe

stream = await client.stream_candles("IDXUSDT", Timeframe.M1)
async with stream:
    async for event in stream:
        print(event.candle.close, event.snapshot)
```

Candle, ticker, and order book streams have bounded queues and share
subscriptions. Superseded snapshots may be coalesced to prevent a slow consumer
from blocking the socket. Handlers registered with `client.events` also run
without blocking the receive loop.

## OPTION orders

```python
from decimal import Decimal
from ebinexpy import Direction, OrderRequest, Timeframe

# Run only on a deliberately selected TEST account.
request = OrderRequest(
    symbol="IDXUSDT",
    direction=Direction.CALL,
    investment=Decimal("1"),
    timeframe=Timeframe.M1,
    price=Decimal("2998.92"),  # current price observed in the feed
)
order = await client.place_order(request)
settlement = await client.wait_order(order.id)
```

Only the window between submission and receipt of the broker ID is serialized;
accepted orders are tracked independently. An ambiguous submission failure
raises `OrderSubmissionUnknownError` and is never retried. A settlement timeout
raises `SettlementTimeoutError.last_order`; a timeout or unknown result is never
converted into a loss.

To enable a REAL account, explicitly construct
`ClientConfig(environment=AccountEnvironment.REAL, allow_real_trading=True)`.
The same guard also protects `client.raw.send()` on the execution destination.

## Raw access and stability

`client.raw.request`, `subscribe`, and `send` reuse authentication, TLS,
readiness, redaction, and account selection. The raw REST/STOMP format is
deliberately unstable and may change between pre-alpha versions. Safe HTTP
requests may reauthenticate once after a 401 response; order execution is never
automatically replayed.

See [examples/read_market.py](examples/read_market.py) and the DEMO order example
with an explicit gate in [examples/demo_order.py](examples/demo_order.py).
The documentation overview and public method examples are available in
[docs/index.md](docs/index.md).
