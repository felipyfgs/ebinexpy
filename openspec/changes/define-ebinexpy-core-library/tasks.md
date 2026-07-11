## 1. Project foundation and evidence fixtures

- [x] 1.1 Create the `src/ebinexpy` feature package skeleton, typed-package marker, build metadata and mirrored test roots.
- [x] 1.2 Add smoke tests proving editable installation, public imports, default TEST configuration and feature composition.
- [x] 1.3 Convert the reviewed REST/STOMP evidence into minimal committed contract fixtures with every credential and identity field replaced by deterministic placeholders.
- [x] 1.4 Add a fixture secret scanner that fails on JWTs, emails, authorization values, cookies, object IDs, UUIDs and unredacted account identifiers.
- [x] 1.5 Configure CI for Python 3.11 and 3.12 to run Ruff, unit tests, contract tests, wheel build and installed-wheel import checks.

## 2. Core types, errors and configuration

- [x] 2.1 Finalize the public exception hierarchy for authentication, connection, protocol, validation, order rejection, ambiguous submission, settlement timeout, real-trading guard and event overflow.
- [x] 2.2 Implement Decimal money parsing/quantization helpers and tests that preserve exact stake, fee, payout and P&L values.
- [x] 2.3 Implement structured logging redaction for credentials, cookies, JWTs, authorization query parameters and user/account/order identifiers.
- [x] 2.4 Expand `ClientConfig` with validated timeouts, heartbeat/reconnect policy, queue capacities, endpoint overrides and explicit REAL-order opt-in.
- [x] 2.5 Define internal protocols for clocks, transports, stores and supervised background tasks so feature tests can use deterministic fakes.

## 3. Typed events and bounded streams

- [x] 3.1 Define public connection, balance, broker-time, candle, ticker, book and order event models with timezone-aware timestamps.
- [x] 3.2 Implement typed handler registration/removal with supervised async execution that never blocks the WebSocket receive loop.
- [x] 3.3 Route handler failures through the configured error/log hook while allowing remaining handlers and socket processing to continue.
- [x] 3.4 Implement bounded async stream primitives with cancellation-safe cleanup and reference-counted subscription release.
- [x] 3.5 Implement latest-value coalescing for market snapshots and lossless lifecycle queues that raise `EventQueueOverflowError` instead of dropping state.
- [x] 3.6 Add concurrency, cancellation, slow-consumer, handler-failure and overflow unit tests.

## 4. HTTP, SockJS and STOMP transport

- [x] 4.1 Implement one pooled `httpx.AsyncClient` with mandatory certificate/hostname verification, configured timeouts and safe response error mapping.
- [x] 4.2 Implement authenticated header/account selection injection without exposing session material in request logs or exceptions.
- [x] 4.3 Implement SockJS URL generation, open/heartbeat/close parsing and JSON-array frame wrapping from contract fixtures.
- [x] 4.4 Implement STOMP 1.2 frame encode/decode, content-length correctness, heartbeat negotiation, MESSAGE/ERROR/RECEIPT handling and escape rules.
- [x] 4.5 Implement the modern `websockets` transport without deprecated `websockets.legacy` imports and with TLS verification enabled.
- [x] 4.6 Implement a subscription registry that deduplicates subscriptions, assigns stable local handles and replays active destinations once per connection generation.
- [x] 4.7 Implement the connection supervisor with heartbeat tasks, bounded exponential backoff plus jitter, readiness transitions and deterministic shutdown.
- [x] 4.8 Add contract tests for the captured CONNECTED handshake, operational destinations, heartbeat traffic, close frames and malformed protocol input.
- [x] 4.9 Add reconnect tests proving a new socket restores TEST, execute, graph and book subscriptions before emitting ready.

## 5. Authentication and secure session stores

- [x] 5.1 Implement login request/response parsing, cookie/JWT extraction and typed authentication failures from sanitized fixtures.
- [x] 5.2 Parse JWT expiry without signature trust, apply a configurable pre-expiry buffer and reject expired or identity-mismatched cached sessions.
- [x] 5.3 Complete `MemorySessionStore` behavior and session serialization tests.
- [x] 5.4 Implement `FileSessionStore` with filesystem-safe identity keys, versioned payloads, atomic replace, private directories and mode `0600` files.
- [x] 5.5 Implement controlled reauthentication and one retry for safe REST requests after 401; explicitly prohibit automatic order replay.
- [x] 5.6 Implement logout so it closes transports and deletes only the selected identity's in-memory and persisted session.
- [x] 5.7 Add tests for wrong-identity caches, corrupted files, expired tokens, concurrent saves, permissions, logout and redacted failures.

## 6. Accounts, profile and balance

- [x] 6.1 Implement account/profile wire parsers for `/users` and `/users/listAccounts` with strict typed normalization and raw-field tolerance.
- [x] 6.2 Implement listing and selecting accounts while keeping REST headers, WebSocket user topic and configured environment consistent.
- [x] 6.3 Implement TEST as the default selection and deterministic errors when the requested environment is unavailable.
- [x] 6.4 Implement profile and balance reads plus `user_balance` event updates using Decimal values.
- [x] 6.5 Add account-switch tests proving old user subscriptions are released and the new environment is subscribed before readiness.

## 7. Assets and historical market data

- [x] 7.1 Implement `availableSymbols` parsing from `configModes.OPTION`, preserving active/closed status, payout, display order and supported timeframes.
- [x] 7.2 Implement `list_assets`, `get_asset`, `get_payout` and `is_market_open` with explicit cache refresh and no static tradability fallback.
- [x] 7.3 Implement broker-time tracking from `broker_server_time` with timezone-aware values and staleness metadata.
- [x] 7.4 Implement aggregated-trade parsing into Decimal OHLCV candles with validation for malformed or incomplete bars.
- [x] 7.5 Implement millisecond-range history pagination, boundary advancement, deduplication and chronological ordering.
- [x] 7.6 Add contract tests for active/closed assets, M1/M5/M15 support, payout changes, empty ranges, pagination boundaries and malformed candles.

## 8. Live candles, ticker and book

- [x] 8.1 Implement reference-counted graph destinations for `{symbol}/{timeframe}` and normalize initial `candles_history` snapshots.
- [x] 8.2 Implement mutable current-candle updates from `trade` while distinguishing snapshot history from live updates in public events.
- [x] 8.3 Implement TEST book subscriptions and typed `book` snapshot plus `book_order` incremental updates.
- [x] 8.4 Implement typed ticker updates containing 24-hour volume and bull/bear totals.
- [x] 8.5 Implement `stream_candles`, `stream_ticker` and `stream_book` on the shared bounded-stream primitives.
- [x] 8.6 Add multi-consumer tests proving one broker subscription is shared, slow consumers do not block receipt and final consumers unsubscribe cleanly.

## 9. OPTION order validation and wire mapping

- [x] 9.1 Finalize order request/result/query models with Decimal financial fields and distinct placement, opening and settlement timestamps.
- [x] 9.2 Implement validation for non-empty active symbols, supported M1/M5/M15 timeframe, CALL/PUT direction and positive broker-supported investment.
- [x] 9.3 Enforce `allow_real_trading=False` before every typed or raw execute send on a REAL account.
- [x] 9.4 Map CALL/PUT to BULL/BEAR, compute the next broker boundary and encode the captured `/user/topic/execute` OPTION payload.
- [x] 9.5 Parse execute confirmations and user-order events into PENDING, OPEN, WIN, LOSE, REFUNDED and CANCELED models.
- [x] 9.6 Add fixture tests covering broker rejection, unexpected payloads, unsupported markets and REAL-order blocking without network I/O.

## 10. Order correlation, history and settlement

- [x] 10.1 Implement a submission lock that serializes only the execute request-to-broker-ID window and never confuses concurrent confirmations.
- [x] 10.2 Implement independent order trackers keyed by broker ID with legal transition checks and terminal-state immutability.
- [x] 10.3 Implement `list_orders` with page/size plus symbol, timeframe, status and order-type filters matching the captured `/orders` query.
- [x] 10.4 Implement `get_order` using cached lifecycle state first and paginated REST reconciliation when required.
- [x] 10.5 Implement `wait_order` using WebSocket events followed by REST reconciliation after reconnect or deadline.
- [x] 10.6 Raise `SettlementTimeoutError` with the last known order instead of fabricating LOSE, and raise `OrderSubmissionUnknownError` for ambiguous send failures without replay.
- [x] 10.7 Add tests for the captured PENDING-to-OPEN-to-WIN sequence, every terminal status, concurrent submissions, lost events, reconnect reconciliation and unknown settlement.

## 11. Raw access and EbinexClient composition

- [x] 11.1 Implement `RawClient.request` on the shared authenticated HTTP transport with typed readiness and response behavior.
- [x] 11.2 Implement raw STOMP subscribe/send operations with explicit instability documentation, cleanup handles and non-bypassable REAL-order safety.
- [x] 11.3 Implement `EbinexClient.connect` to authenticate, resolve the configured account, start transports, register core destinations and become ready atomically.
- [x] 11.4 Implement idempotent `disconnect`, session-clearing `logout`, connection/authentication properties and `wait_until_ready`.
- [x] 11.5 Expose stable convenience methods on `EbinexClient` for accounts, assets, market streams, order placement/history and settlement while preserving feature services for advanced use.
- [x] 11.6 Finalize root and feature exports so public types are reachable without importing private wire or transport modules.
- [x] 11.7 Add facade tests proving lifecycle rollback on partial connect failure, clean context-manager shutdown and absence of duplicate tasks/subscriptions.

## 12. Acceptance, documentation and release readiness

- [x] 12.1 Add an opt-in live DEMO read-only suite for login, accounts, assets, payout, broker time, candles, ticker/book and history.
- [x] 12.2 Add a separately gated DEMO settlement test that creates exactly one minimum-stake OPTION order and verifies PENDING, OPEN, terminal status and balance reconciliation.
- [x] 12.3 Add a test that rejects live-order execution unless the environment is TEST or the explicit REAL opt-in is present; CI MUST never enable REAL trading.
- [x] 12.4 Document installation, lifecycle, session stores, market streams, order flow, error semantics, concurrency, raw instability and security guidance.
- [x] 12.5 Add runnable examples for read-only market data and one prominently gated DEMO order without embedding environment loading in the runtime library.
- [x] 12.6 Run Ruff, all non-live tests, fixture secret scan, Python 3.11/3.12 matrices, wheel/sdist builds and clean-environment import tests.
- [x] 12.7 Run the opt-in DEMO acceptance suite, attach sanitized evidence, confirm every OpenSpec scenario and prepare the first pre-alpha changelog.
