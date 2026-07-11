## Context

The project starts from an empty `ebinexpy` workspace. The previous prototype
proved basic endpoint feasibility but is not a compatibility target. The live
DEMO capture documented in `docs/research/` confirms cookie/JWT authentication,
account selection by header, REST history, SockJS/STOMP market delivery, order
states and subscription replay after a network outage.

The library will be embedded by long-running bots, workers and service APIs.
It must own protocol correctness, lifecycle and typed domain boundaries while
leaving strategy, risk sizing, persistence of business data and process hosting
to consumers.

## Goals / Non-Goals

**Goals:**

- Provide the full operational surface needed to build a reliable asynchronous
  `OPTION` robot.
- Preserve order-event correctness across concurrency, timeout and reconnect.
- Expose stable typed models while containing reverse-engineered wire formats.
- Make secure session handling and TLS-safe transport the defaults.
- Remain extensible when the platform adds or changes unmodeled operations.

**Non-Goals:**

- Running an HTTP server, scheduler, strategy engine, risk manager or database.
- Funding, withdrawal, KYC, recovery, notifications, missions, strikes or
  championships.
- Retraction, stop, early close, SPOT or any order mode other than `OPTION`.
- Synchronous wrappers or compatibility with the prototype package.

## Decisions

### 1. One async facade with composed subsystems

`EbinexClient` is the public lifecycle owner and composes private auth, REST,
WebSocket, accounts, market and order components. Public behavior is delegated
to those components instead of implemented through mixin inheritance. The
distribution and import package are both `ebinexpy`; v1 supports Python 3.11+.

The client is an async context manager and exposes `connect`, `disconnect`,
`logout`, readiness properties and `wait_until_ready`. Repeated lifecycle calls
are idempotent. `disconnect` preserves the stored session; `logout` also clears
it.

Alternative rejected: separate public clients for REST, market and orders. That
would allow incompatible active accounts and duplicate connection state.

### 2. Explicit configuration and account safety

`ClientConfig` holds endpoints, timeouts, reconnect policy, queue sizes, store
and target environment. The default environment is `TEST` and
`allow_real_trading` defaults to false. Reading a REAL account is allowed after
explicit selection; placing an order on it without the opt-in raises
`RealTradingDisabledError` before network I/O.

Credentials may be passed by the host application but are never read from
environment variables by the runtime library itself. Examples may load `.env`.
Logs redact credentials, cookies, JWTs, account/user/order IDs and authorization
query parameters.

### 3. Pluggable identity-scoped session stores

`SessionStore` is an async protocol with `load(identity)`, `save(identity,
session)` and `delete(identity)`. `MemorySessionStore` and `FileSessionStore`
ship in v1. File writes are atomic, per identity, and mode `0600`; parent
directories are private where the operating system supports permissions.

Loaded sessions must match the requested identity. Expiry is derived from JWT
claims when available, with a pre-expiry refresh buffer; an authenticated 401
invalidates the session and permits one controlled re-login/retry for safe REST
requests. Order submission is never automatically replayed after an ambiguous
transport failure.

### 4. Persistent verified transports

One shared `httpx.AsyncClient` provides pooling and authenticated headers. TLS
certificate and hostname verification are mandatory. SockJS framing and STOMP
1.2 run over a maintained WebSocket API without deprecated legacy imports.

The WebSocket supervisor owns connect/heartbeat/receive tasks, exponential
backoff with jitter, connection generation and a subscription registry. A
successful reconnect replays active subscriptions once, then emits a ready
event. Failed attempts continue until configuration limits are reached; pending
waiters receive a typed terminal connection error when retries are exhausted.

### 5. Typed event dispatcher plus bounded streams

The receive loop parses and routes frames but never awaits consumer business
logic. `add_event_handler` returns a removable token; handlers run in supervised
tasks and handler failures are reported through logging/error hooks without
terminating the socket.

Async iterators for candles, ticker and book use bounded queues. Superseded
market snapshots may be coalesced to the latest value under pressure. Connection
and order lifecycle events use lossless internal routing; overflow closes the
affected consumer with `EventQueueOverflowError` rather than silently dropping
state. Cancelling or closing a stream always unregisters its subscription.

### 6. Stable market-data contract

Asset methods normalize the `OPTION` portion of `availableSymbols`, retaining
market status, payout and supported timeframes. Closed or unsupported assets
fail order preflight. Historical candle requests accept timezone-aware
datetimes, paginate by broker millisecond boundaries, deduplicate open times and
return chronological `Candle` models.

Live graph subscriptions emit an initial history batch and then mutable current
candle updates. The library labels these semantics explicitly so consumers can
choose snapshot or update behavior. Broker time is tracked from
`broker_server_time` and used for candle-boundary calculations.

### 7. Correlated `OPTION` order state machine

`place_order(OrderRequest)` accepts symbol, `CALL`/`PUT`, positive decimal
investment and supported timeframe. Wire conversion maps directions to
`BULL`/`BEAR`, decimal investment to the broker string, and the next boundary to
the command's `candleEndTime`.

Because the execute channel does not expose a client correlation key before the
broker reply, submissions are serialized only until a broker order ID is
received. Each accepted order then has an independent state tracker keyed by
that ID. Legal progress is `PENDING -> OPEN -> terminal`; terminal statuses are
`WIN`, `LOSE`, `REFUNDED` and `CANCELED`.

`wait_order` first observes WebSocket state, then reconciles through REST after
reconnect or timeout. An unresolved deadline raises `SettlementTimeoutError`
containing the last known order; it never fabricates `LOSE`. Ambiguous send
failure raises `OrderSubmissionUnknownError` and is not retried automatically.
Money, fees, payout and P&L use `Decimal` rather than binary floats.

### 8. Public raw access is quarantined

`client.raw` exposes authenticated request and STOMP-send primitives for
research and forward compatibility. It shares lifecycle, account headers, TLS,
redaction and connection checks, but its wire inputs/outputs have no stability
guarantee. It cannot bypass the REAL trading guard for known order destinations.

## Risks / Trade-offs

- **Reverse-engineered protocol changes** -> Keep wire parsing isolated, retain
  sanitized contract fixtures and fail with typed protocol errors that preserve
  safe diagnostics.
- **High-frequency market traffic overwhelms consumers** -> Use bounded queues,
  snapshot coalescing and per-stream cancellation without blocking receive.
- **Reconnect loses an order transition** -> Replay subscriptions before ready
  and reconcile tracked orders over REST.
- **Execute confirmations cross under concurrency** -> Serialize only the
  uncorrelated submission window and route all later events by broker ID.
- **Session material is sensitive** -> Identity-scoped stores, restrictive
  permissions, atomic writes and comprehensive redaction.
- **Raw access weakens abstraction stability** -> Mark it unstable, isolate it
  under `client.raw` and keep safety invariants non-bypassable.

## Migration Plan

1. Treat this as a new package rather than migrating prototype internals.
2. Implement lifecycle/session and protocol parsers against sanitized fixtures.
3. Add market operations and bounded event streams.
4. Add order placement/state reconciliation behind DEMO-only integration gates.
5. Run unit/contract tests on Python 3.11 and 3.12, followed by opt-in live DEMO
   tests that create at most one minimum-stake order.
6. Publish a `0.x` release only after TLS, reconnect, concurrency and redaction
   acceptance tests pass. Rollback is package-version pinning; session-store
   formats must carry a version field.

## Open Questions

None for the operational v1 contract. Features outside the confirmed `OPTION`
surface require a separate evidence capture and OpenSpec change.
