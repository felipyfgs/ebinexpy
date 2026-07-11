## ADDED Requirements

### Requirement: Quarantined raw protocol access
The client SHALL expose authenticated REST requests and STOMP sends under
`client.raw`, explicitly outside the stable compatibility contract while still
enforcing client lifecycle, account selection, TLS and redaction invariants.

#### Scenario: Raw authenticated REST request
- **WHEN** a connected consumer invokes an unmodeled REST path through `client.raw`
- **THEN** the request uses the selected account and authenticated shared transport without exposing credentials in logs

#### Scenario: Raw access before readiness
- **WHEN** raw transport is used before the relevant transport is ready
- **THEN** the client raises a typed not-connected error

### Requirement: Raw access cannot bypass real-order safety
The raw STOMP surface MUST enforce the real-trading guard for known order
destinations even though its payload schema is unstable.

#### Scenario: Raw execute send on REAL without opt-in
- **WHEN** a consumer sends to the execute destination on a REAL account while real trading is disabled
- **THEN** `RealTradingDisabledError` is raised before the frame is transmitted
