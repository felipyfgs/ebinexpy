# Changelog

## 0.1.0 - Unreleased

- Added the async `EbinexClient` facade with TEST-first lifecycle.
- Added pluggable memory and secure file session stores.
- Added typed account, market, event and OPTION order models.
- Added pooled HTTP and supervised SockJS/STOMP WebSocket transports.
- Added bounded shared market streams and correlated order settlement tracking.
- Added guarded, explicitly unstable raw REST/STOMP access.
- Added trusted PyPI publishing and package project links.
- Improved atomic session persistence and supervised WebSocket reconnection.
- Fixed market stream routing, cancellation cleanup and subscription ID reuse.
- Fixed ambiguous order submission handling, history lookup and terminal reconciliation.
