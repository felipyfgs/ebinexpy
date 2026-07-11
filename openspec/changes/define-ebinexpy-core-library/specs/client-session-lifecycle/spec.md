## ADDED Requirements

### Requirement: Authenticated client lifecycle
The library SHALL provide one asynchronous client that authenticates, selects
an account, establishes REST and WebSocket transports, reports readiness and
supports idempotent connect and disconnect operations.

#### Scenario: Connect to the default demo account
- **WHEN** a client with valid credentials and default configuration connects
- **THEN** it selects a `TEST` account and becomes ready only after authentication and required STOMP subscriptions succeed

#### Scenario: Repeated lifecycle calls
- **WHEN** `connect` or `disconnect` is called more than once in the same state
- **THEN** the call completes without creating duplicate transports, tasks or subscriptions

### Requirement: Secure pluggable sessions
The library SHALL define an identity-scoped async session-store protocol and
ship memory and atomic file implementations. A loaded session MUST match the
requested identity, and file material MUST use restrictive permissions.

#### Scenario: Reject a different identity's cached session
- **WHEN** a store returns a valid token associated with another identity
- **THEN** the client ignores that session and authenticates the requested identity

#### Scenario: Persist a file session
- **WHEN** authentication succeeds with a file session store
- **THEN** the session is atomically saved in an identity-specific file with mode `0600` where supported

### Requirement: Reconnect and restore subscriptions
The client SHALL supervise the WebSocket connection with bounded exponential
backoff and jitter and SHALL restore the active subscription registry exactly
once after each successful reconnect.

#### Scenario: Temporary network outage
- **WHEN** the socket closes and a later reconnect succeeds
- **THEN** all active user and market subscriptions are restored before the client emits a ready connection event

#### Scenario: Retry budget exhausted
- **WHEN** every configured reconnect attempt fails
- **THEN** the client becomes disconnected and pending waiters receive a typed connection error

### Requirement: Session termination semantics
Disconnect SHALL preserve the stored authenticated session, while logout SHALL
disconnect and delete both in-memory and persisted session material.

#### Scenario: Logout a connected client
- **WHEN** the consumer calls `logout`
- **THEN** transports close and the selected identity's stored session is deleted
