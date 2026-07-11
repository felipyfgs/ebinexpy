## Why

`ebinexpy` must be the embeddable operational foundation for trading robots and
services, not an HTTP API or a collection of reverse-engineering scripts. A
live DEMO capture has now established the minimum REST, SockJS/STOMP and order
lifecycle contracts needed to design that foundation safely.

## What Changes

- Create a new Python distribution and import package named `ebinexpy` with an
  asyncio-first `EbinexClient`.
- Expose typed account, market-data and `OPTION` order operations required to
  build a complete robot.
- Add typed events and bounded async streams over one shared WebSocket
  connection.
- Add automatic reconnection with deterministic subscription restoration and
  REST reconciliation of order state.
- Add a pluggable session-store contract with secure memory and file
  implementations.
- Add an explicitly unstable `client.raw` escape hatch for authenticated
  protocol operations not yet promoted into the typed API.
- Default to the DEMO/`TEST` environment and require explicit opt-in before a
  real-money order can be sent.
- **BREAKING**: this is a clean package and API design; the old `pyebinex`/
  `ebinex` prototype surface is not retained as a compatibility contract.

## Capabilities

### New Capabilities

- `client-session-lifecycle`: Authentication, account selection, secure session
  persistence, readiness, disconnect/logout and reconnection behavior.
- `market-data-access`: Asset discovery, payout/market state, broker time,
  historical candles and bounded live candle/ticker/book streams.
- `option-order-lifecycle`: Validated `OPTION` submission, correlation,
  lifecycle events, history/query and settlement semantics.
- `typed-event-dispatch`: Non-blocking typed handlers and streams with explicit
  overflow and error behavior.
- `unstable-raw-transport`: Guarded authenticated REST/STOMP access for
  unmodeled platform operations.

### Modified Capabilities

None. This OpenSpec workspace has no existing product capability specifications.

## Impact

- Introduces the `src/ebinexpy` runtime package, public models and typed errors.
- Requires maintained HTTP and WebSocket dependencies with TLS verification.
- Establishes DEMO capture fixtures and protocol-contract tests without storing
  credentials, tokens or account identifiers.
- Excludes API-server concerns and non-operational Ebinex areas such as funding,
  KYC, promotions, championships, missions and notifications.
