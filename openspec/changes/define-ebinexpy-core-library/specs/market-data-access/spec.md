## ADDED Requirements

### Requirement: Discover OPTION assets
The library SHALL expose typed assets whose market status, payout and supported
timeframes are derived from `configModes.OPTION` rather than static constants.

#### Scenario: List open and closed assets
- **WHEN** the broker returns active and inactive symbols
- **THEN** `list_assets` preserves their status and only marks active `OPTION` configurations as tradable

#### Scenario: Read a payout
- **WHEN** a consumer requests payout for an active symbol and timeframe
- **THEN** the client returns the live `OPTION` payout associated with that configuration

### Requirement: Historical candles
The library SHALL fetch OHLCV history using broker millisecond ranges,
paginate without gaps, deduplicate candle open times and return chronological
typed candles.

#### Scenario: Range exceeds one response
- **WHEN** a requested range contains more candles than the per-request limit
- **THEN** the client advances from the newest returned timestamp until the range is exhausted without duplicating boundary candles

### Requirement: Live market streams
The library SHALL expose bounded async streams for candle, ticker and book data
over shared STOMP subscriptions and SHALL unregister them when consumers close
or cancel iteration.

#### Scenario: Start a candle stream
- **WHEN** the first consumer subscribes to a symbol/timeframe
- **THEN** the client exposes the history snapshot followed by live `trade` updates through typed candle events

#### Scenario: Slow market consumer
- **WHEN** a market stream reaches its configured capacity
- **THEN** superseded snapshots may be coalesced to the latest state without blocking the WebSocket receive loop

### Requirement: Broker clock
The library SHALL expose the last confirmed broker timestamp and emit typed
updates from `broker_server_time` for boundary calculations.

#### Scenario: Broker time received
- **WHEN** a `broker_server_time` event arrives
- **THEN** `get_broker_time` and the corresponding event expose its timezone-aware instant
