## ADDED Requirements

### Requirement: Typed non-blocking handlers
The library SHALL dispatch connection, balance, broker-time, market and order
events as public types without awaiting consumer business logic in the socket
receive loop.

#### Scenario: Register and remove a handler
- **WHEN** a consumer registers a handler and later removes its returned token
- **THEN** matching events invoke it only while the token remains registered

#### Scenario: Handler raises an exception
- **WHEN** a consumer handler fails
- **THEN** the failure is reported through the configured error/log hook and other handlers and socket processing continue

### Requirement: Explicit bounded-queue behavior
Each async event stream SHALL have configured capacity and SHALL distinguish
coalescible market state from lossless lifecycle state.

#### Scenario: Order consumer cannot keep up
- **WHEN** an order-event consumer exhausts its lossless queue capacity
- **THEN** that stream terminates with `EventQueueOverflowError` instead of silently dropping an order transition

#### Scenario: Stream cancellation
- **WHEN** iteration is cancelled or the generator is closed
- **THEN** its handler, queue and broker subscription reference are released
