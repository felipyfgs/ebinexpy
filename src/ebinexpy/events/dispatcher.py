"""Typed event-dispatch contracts."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .models import Event

EventHandler = Callable[[Event], Awaitable[None] | None]
ErrorHandler = Callable[[Exception, EventHandler, Event], Any]
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HandlerToken:
    value: int


class EventDispatcher:
    """Registry scaffold for non-blocking typed handlers."""

    def __init__(self, error_handler: ErrorHandler | None = None) -> None:
        self._next_token = 0
        self._handlers: dict[HandlerToken, EventHandler] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._error_handler = error_handler

    def add(self, handler: EventHandler) -> HandlerToken:
        token = HandlerToken(self._next_token)
        self._next_token += 1
        self._handlers[token] = handler
        return token

    def remove(self, token: HandlerToken) -> bool:
        return self._handlers.pop(token, None) is not None

    def emit(self, event: Event) -> None:
        for handler in tuple(self._handlers.values()):
            task = asyncio.create_task(self._run(handler, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _run(self, handler: EventHandler, event: Event) -> None:
        try:
            result = handler(event)
            if result is not None:
                await result
        except Exception as exc:  # consumer failures are isolated
            if self._error_handler:
                self._error_handler(exc, handler, event)
            else:
                logger.exception("Event handler failed", exc_info=exc)

    async def close(self) -> None:
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        self._handlers.clear()
