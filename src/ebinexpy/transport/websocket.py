"""Modern WebSocket transport boundary."""

import asyncio
import ssl

from websockets.asyncio.client import ClientConnection, connect

from ..core.exceptions import ConnectionError, ProtocolError
from .sockjs import SockJSKind, build_websocket_url, parse, wrap
from .stomp import StompFrame, connect_frame, decode, encode


class WebSocketTransport:
    def __init__(self, base_url: str, timeout: float, heartbeat_interval: float) -> None:
        self._base_url = base_url
        self._timeout = timeout
        self._heartbeat_ms = int(heartbeat_interval * 1000)
        self._connection: ClientConnection | None = None

    @property
    def connected(self) -> bool:
        return self._connection is not None

    async def connect(self, token: str) -> None:
        url = build_websocket_url(self._base_url, token)
        ssl_context = ssl.create_default_context()
        try:
            connection = await asyncio.wait_for(
                connect(url, ssl=ssl_context, ping_interval=None, close_timeout=5),
                self._timeout,
            )
            opened = parse(str(await asyncio.wait_for(connection.recv(), self._timeout)))
            if opened.kind is not SockJSKind.OPEN:
                raise ProtocolError("SockJS did not send an open frame")
            await connection.send(wrap(encode(connect_frame(self._heartbeat_ms))))
            while True:
                incoming = parse(str(await asyncio.wait_for(connection.recv(), self._timeout)))
                for message in incoming.messages:
                    frame = decode(message)
                    if frame.command == "CONNECTED":
                        self._connection = connection
                        return
                    if frame.command == "ERROR":
                        raise ProtocolError("STOMP rejected the connection")
        except Exception as exc:
            if "connection" in locals():
                await connection.close()
            if isinstance(exc, (ProtocolError, asyncio.CancelledError)):
                raise
            raise ConnectionError("WebSocket connection failed") from exc

    async def send(self, frame: StompFrame) -> None:
        if self._connection is None:
            raise ConnectionError("WebSocket is not connected")
        await self._connection.send(wrap(encode(frame)))

    async def receive(self) -> tuple[StompFrame, ...]:
        if self._connection is None:
            raise ConnectionError("WebSocket is not connected")
        incoming = parse(str(await self._connection.recv()))
        if incoming.kind is SockJSKind.CLOSE:
            raise ConnectionError("SockJS closed the connection")
        return tuple(decode(message) for message in incoming.messages if message.strip())

    async def heartbeat(self) -> None:
        if self._connection is None:
            raise ConnectionError("WebSocket is not connected")
        await self._connection.send(wrap("\n"))

    async def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None:
            await connection.close()
