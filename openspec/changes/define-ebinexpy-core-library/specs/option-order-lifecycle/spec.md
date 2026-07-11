## ADDED Requirements

### Requirement: Validate and submit OPTION orders
The library SHALL accept typed `OPTION` requests with symbol, direction,
investment and timeframe, preflight them against the live asset contract and
map them to the confirmed STOMP command.

#### Scenario: Valid demo CALL
- **WHEN** a consumer submits a positive investment for an active symbol/timeframe in `TEST`
- **THEN** the client sends one `OPTION` command with `BULL`, broker boundary time and the selected demo account

#### Scenario: Unsupported market configuration
- **WHEN** the symbol is closed or the timeframe is not active for `OPTION`
- **THEN** the client raises a typed validation/order error before sending a command

#### Scenario: Real order without opt-in
- **WHEN** the active account is `REAL` and `allow_real_trading` is false
- **THEN** the client raises `RealTradingDisabledError` before network I/O

### Requirement: Correlate concurrent submissions
The client SHALL prevent execute-channel confirmations from crossing between
callers by serializing the uncorrelated submission window until a broker order
ID is received, then tracking each order independently by ID.

#### Scenario: Two simultaneous placement calls
- **WHEN** two coroutines place orders concurrently
- **THEN** each coroutine receives the broker result for its own serialized command and subsequent events are routed by order ID

### Requirement: Preserve the broker order state machine
Orders SHALL represent `PENDING`, `OPEN`, `WIN`, `LOSE`, `REFUNDED` and
`CANCELED` distinctly, including separate placement, candle-open and
settlement timestamps.

#### Scenario: Automatic M1 settlement
- **WHEN** a captured order progresses from placement through the next M1 candle
- **THEN** typed events expose `PENDING`, then `OPEN`, then the broker's terminal status with entry/close prices and Decimal P&L

### Requirement: Reconcile and time out safely
`wait_order` SHALL combine WebSocket state with REST reconciliation after
disconnect or deadline. Unknown settlement MUST NOT be converted to `LOSE` and
an ambiguous send failure MUST NOT be retried automatically.

#### Scenario: Settlement remains unknown
- **WHEN** neither WebSocket nor REST confirms a terminal status before the deadline
- **THEN** `SettlementTimeoutError` contains the last known order state

#### Scenario: Connection drops during command send
- **WHEN** the client cannot prove whether the broker accepted a submitted command
- **THEN** it raises `OrderSubmissionUnknownError` without sending the command again

### Requirement: Query order history
The library SHALL expose typed single-order lookup and paginated order history
with symbol, timeframe, status and order-type filters.

#### Scenario: Fetch one page of settled orders
- **WHEN** a consumer requests settled history with page and size
- **THEN** the client returns typed orders preserving payout composition, fees, refund, timestamps and terminal P&L
