"""OPTION order feature."""

from .models import Direction, Order, OrderQuery, OrderRequest, OrderStatus, Settlement


def __getattr__(name: str) -> object:
    if name == "OrderService":
        from .service import OrderService

        return OrderService
    raise AttributeError(name)


__all__ = [
    "Direction",
    "Order",
    "OrderQuery",
    "OrderRequest",
    "OrderService",
    "OrderStatus",
    "Settlement",
]
