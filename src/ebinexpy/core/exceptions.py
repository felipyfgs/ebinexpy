"""Typed exception hierarchy."""


class EbinexError(Exception):
    """Base error for every public ebinexpy failure."""


class AuthenticationError(EbinexError):
    pass


class TransportError(EbinexError):
    pass


class ConnectionError(TransportError):
    pass


class NotConnectedError(ConnectionError):
    pass


class ProtocolError(EbinexError):
    pass


class ValidationError(EbinexError):
    pass


class OrderError(EbinexError):
    pass


class OrderRejectedError(OrderError):
    pass


class SettlementTimeoutError(OrderError):
    def __init__(self, message: str, last_order: object | None = None) -> None:
        super().__init__(message)
        self.last_order = last_order


class OrderSubmissionUnknownError(OrderError):
    pass


class RealTradingDisabledError(OrderError):
    pass


class EventQueueOverflowError(EbinexError):
    pass
