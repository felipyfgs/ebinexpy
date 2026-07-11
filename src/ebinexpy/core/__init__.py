"""Shared internal primitives."""

from .exceptions import (
    AuthenticationError,
    ConnectionError,
    EbinexError,
    EventQueueOverflowError,
    NotConnectedError,
    OrderError,
    OrderRejectedError,
    OrderSubmissionUnknownError,
    ProtocolError,
    RealTradingDisabledError,
    SettlementTimeoutError,
    TransportError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "ConnectionError",
    "EbinexError",
    "EventQueueOverflowError",
    "NotConnectedError",
    "OrderError",
    "OrderRejectedError",
    "OrderSubmissionUnknownError",
    "ProtocolError",
    "RealTradingDisabledError",
    "SettlementTimeoutError",
    "TransportError",
    "ValidationError",
]
