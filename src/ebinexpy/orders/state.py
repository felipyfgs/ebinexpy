"""Order state-machine and correlation primitives."""

import asyncio
from dataclasses import replace

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
            merged_request = replace(
                order.request,
                price=(
                    order.request.price
                    if order.request.price is not None
                    else self.order.request.price
                ),
            )
            merged = replace(
                order,
                request=merged_request,
                opened_at=order.opened_at or self.order.opened_at,
                settled_at=order.settled_at or self.order.settled_at,
                open_price=(
                    order.open_price if order.open_price is not None else self.order.open_price
                ),
                close_price=(
                    order.close_price if order.close_price is not None else self.order.close_price
                ),
                profit=order.profit if order.profit is not None else self.order.profit,
                fees=order.fees if order.fees is not None else self.order.fees,
                payout=order.payout if order.payout is not None else self.order.payout,
                scheduled_open_at=order.scheduled_open_at or self.order.scheduled_open_at,
                expires_at=order.expires_at or self.order.expires_at,
            )
            if merged != self.order:
                async with self.changed:
                    self.order = merged
                    self.changed.notify_all()
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
