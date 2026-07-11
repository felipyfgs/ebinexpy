# Changelog

## 0.1.2 - 2026-07-11

- Removed obsolete Node.js and Playwright research tooling.
- Restricted source distributions to package sources and required release metadata.

## 0.1.1 - 2026-07-11

- Clarified installation, version pinning and upgrade commands.
- Documented portable Python commands for Linux, macOS and Windows.
- Updated the packaged project documentation published on PyPI.

## 0.1.0 - 2026-07-11

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
