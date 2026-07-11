"""Bounded event-stream primitives and overflow policies."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Generic, TypeVar

from ..core.exceptions import EventQueueOverflowError

T = TypeVar("T")
Cleanup = Callable[[], Awaitable[None] | None]
_CLOSED = object()


class EventStream(Generic[T]):
    def __init__(
        self,
        capacity: int,
        *,
        coalesce: bool = False,
        cleanup: Cleanup | None = None,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._queue: asyncio.Queue[T | object] = asyncio.Queue(capacity)
        self._coalesce = coalesce
        self._cleanup = cleanup
        self._closed = False
        self._error: Exception | None = None

    def publish(self, item: T) -> None:
        if self._closed:
            return
        if self._queue.full():
            if not self._coalesce:
                self._error = EventQueueOverflowError("Lossless event stream capacity exceeded")
                self._closed = True
                return
            while not self._queue.empty():
                self._queue.get_nowait()
        self._queue.put_nowait(item)

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
        if not self._queue.full():
            self._queue.put_nowait(_CLOSED)
        cleanup, self._cleanup = self._cleanup, None
        if cleanup:
            result = cleanup()
            if result is not None:
                await result

    def __aiter__(self) -> AsyncIterator[T]:
        async def iterate() -> AsyncIterator[T]:
            try:
                while True:
                    yield await self.__anext__()
            except StopAsyncIteration:
                return
            finally:
                await self.close()

        return iterate()

    async def __anext__(self) -> T:
        if self._error:
            error, self._error = self._error, None
            await self.close()
            raise error
        if self._closed and self._queue.empty():
            raise StopAsyncIteration
        try:
            item = await self._queue.get()
        except asyncio.CancelledError:
            await asyncio.shield(self.close())
            raise
        if item is _CLOSED:
            raise StopAsyncIteration
        return item  # type: ignore[return-value]

    async def __aenter__(self) -> "EventStream[T]":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
