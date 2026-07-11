# `EbinexClient` methods

Quick reference for the library's main public methods. Because the API is
asynchronous, use `await` with methods declared with `async`.

[Back to the documentation home](index.md)

## Contents

- [Creating the client](#creating-the-client)
- [Connection and session](#connection-and-session)
- [Accounts](#accounts)
- [Market data](#market-data)
- [Real-time streams](#real-time-streams)
- [Orders](#orders)
- [Recommended usage](#recommended-usage)
- [Raw access](#raw-access)

## Creating the client

```python
from ebinexpy import EbinexClient

client = EbinexClient("email@example.com", "password")
```

The constructor only configures the client; the connection is opened by
`connect()` or automatically when using `async with`.

## Connection and session

### `await client.connect()`

Authenticates the user, selects the configured account, and starts the real-time
connection.

### `await client.wait_until_ready(timeout=None)`

Waits until the client is ready. `timeout` is the maximum time in seconds.

### `await client.disconnect()`

Closes the real-time connection but preserves the authenticated session.

### `await client.logout()`

Disconnects and removes the current user's saved session.

### `await client.close()`

Closes the HTTP and WebSocket connections and shuts down the event handlers.

The `client.authenticated` and `client.connected` properties indicate whether
the client is authenticated and connected, respectively.

```python
await client.connect()

print(client.authenticated)  # True
print(client.connected)      # True

await client.disconnect()
```

## Accounts

### `await client.list_accounts()`

Returns the list of accounts available to the user.

### `await client.select_account(environment)`

Selects the account for the specified environment, usually
`AccountEnvironment.TEST` or `AccountEnvironment.REAL`.

### `await client.get_profile()`

Returns the user's profile data.

### `await client.get_balance()`

Returns the balance of the selected account.

```python
from ebinexpy import AccountEnvironment

accounts = await client.list_accounts()
for account in accounts:
    print(account.environment, account.balance)

account = await client.select_account(AccountEnvironment.TEST)
profile = await client.get_profile()
balance = await client.get_balance()

print(account.id)
print(profile.email)
print(balance.amount, balance.currency)
```

## Market data

### `await client.list_assets(refresh=False)`

Lists the available assets. Use `refresh=True` to bypass the cache.

### `await client.get_asset(symbol, refresh=False)`

Retrieves an asset by symbol, for example `"IDXUSDT"`.

### `await client.get_payout(symbol, timeframe)`

Returns the asset payout for the specified timeframe.

### `await client.is_market_open(symbol, timeframe)`

Indicates whether the asset is open for trading during that timeframe.

### `client.get_broker_time()`

Returns the latest time received from the broker, or `None` when no time has
been received yet.

### `await client.get_candles(symbol, timeframe, start, end, limit=500)`

Returns historical candles between `start` and `end`. Dates must be
timezone-aware.

```python
from datetime import UTC, datetime, timedelta

from ebinexpy import Timeframe

assets = await client.list_assets()
tradable = [asset for asset in assets if asset.tradable]

asset = await client.get_asset("IDXUSDT")
payout = await client.get_payout(asset.symbol, Timeframe.M1)
is_open = await client.is_market_open(asset.symbol, Timeframe.M1)
broker_time = client.get_broker_time()

end = datetime.now(UTC)
start = end - timedelta(hours=1)
candles = await client.get_candles(
    asset.symbol,
    Timeframe.M1,
    start,
    end,
)

print([item.symbol for item in tradable])
print(asset.label, payout, is_open)
print(broker_time.value if broker_time else "broker time not received yet")
print(candles[-1].close if candles else "no candles")
```

## Real-time streams

### `await client.stream_candles(symbol, timeframe)`

Opens a stream of candle updates.

### `await client.stream_ticker(symbol, timeframe)`

Opens a ticker stream with volume and buy and sell totals.

### `await client.stream_book(symbol, timeframe)`

Opens a stream of order book updates.

Consumption example:

```python
from ebinexpy import Timeframe

stream = await client.stream_candles("IDXUSDT", Timeframe.M1)
async with stream:
    async for event in stream:
        print(event.candle.close)
```

Ticker and order book streams follow the same pattern. Consume each stream in
the appropriate application task:

```python
ticker_stream = await client.stream_ticker("IDXUSDT", Timeframe.M1)
async with ticker_stream:
    async for event in ticker_stream:
        print(event.ticker.volume_24h)
```

```python
book_stream = await client.stream_book("IDXUSDT", Timeframe.M1)
async with book_stream:
    async for event in book_stream:
        print(event.update.direction, event.update.investment)
```

## Orders

### `await client.place_order(request)`

Submits an `OrderRequest` and returns the created order.

```python
from decimal import Decimal
from ebinexpy import Direction, OrderRequest, Timeframe

request = OrderRequest(
    symbol="IDXUSDT",
    direction=Direction.CALL,
    investment=Decimal("1.00"),
    timeframe=Timeframe.M1,
)
order = await client.place_order(request)
```

### `await client.list_orders(query=None)`

Lists orders. An `OrderQuery` can be used to filter and paginate the results.

### `await client.get_order(order_id, refresh=False)`

Retrieves an order by ID. Returns `None` when the order is not found.

### `await client.wait_order(order_id, timeout=None)`

Waits for the order to finish and returns its `Settlement`.

```python
from ebinexpy import OrderQuery, OrderStatus

orders = await client.list_orders(
    OrderQuery(statuses=(OrderStatus.OPEN,))
)

if orders:
    current = await client.get_order(orders[0].id, refresh=True)
    if current is not None:
        settlement = await client.wait_order(current.id, timeout=40)
        print(settlement.order.status, settlement.profit)
```

## Recommended usage

The context manager connects and closes the client automatically:

```python
import asyncio
import os

from ebinexpy import EbinexClient


async def main() -> None:
    async with EbinexClient(
        os.environ["EBINEX_EMAIL"],
        os.environ["EBINEX_PASSWORD"],
    ) as client:
        balance = await client.get_balance()
        print(balance.amount)


asyncio.run(main())
```

> **Warning:** the `TEST` account is the default. Operations on the `REAL`
> account require explicit configuration and authorization.

## Raw access

For advanced integrations, use `client.raw.request()`,
`client.raw.subscribe()`, and `client.raw.send()`. This interface is unstable
and may change between versions; prefer `EbinexClient` methods whenever
possible.

```python
response = await client.raw.request("GET", "/users")
response.raise_for_status()
print(response.json())

subscription = await client.raw.subscribe("/user/topic/TEST")
async with subscription:
    async for frame in subscription:
        print(frame.body)
```
