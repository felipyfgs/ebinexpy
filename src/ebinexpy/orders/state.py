"""Order state-machine and correlation primitives."""

import asyncio

from ..core.exceptions import ProtocolError
from .models import Order, OrderStatus
from .wire import TERMINAL_STATUSES

LEGAL = {
    OrderStatus.PENDING: {OrderStatus.PENDING, OrderStatus.OPEN, *TERMINAL_STATUSES},
    OrderStatus.OPEN: {OrderStatus.OPEN, *TERMINAL_STATUSES},
}


class OrderTracker:
    def __init__(self, order: Order) -> None:
        self.order = order
        self.changed = asyncio.Condition()

    async def update(self, order: Order) -> None:
        if order.id != self.order.id:
            raise ProtocolError("Order tracker received a different broker ID")
        if self.order.status in TERMINAL_STATUSES:
            if order.status is not self.order.status:
                raise ProtocolError("Terminal order state cannot change")
            return
        if order.status not in LEGAL[self.order.status]:
            raise ProtocolError(f"Illegal order transition: {self.order.status} -> {order.status}")
        async with self.changed:
            self.order = order
            self.changed.notify_all()

    async def wait_terminal(self) -> Order:
        async with self.changed:
            await self.changed.wait_for(lambda: self.order.status in TERMINAL_STATUSES)
            return self.order
