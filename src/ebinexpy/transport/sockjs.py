"""SockJS framing primitives."""

import json
import secrets
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote

from ..core.exceptions import ProtocolError


class SockJSKind(StrEnum):
    OPEN = "open"
    HEARTBEAT = "heartbeat"
    MESSAGE = "message"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class SockJSFrame:
    kind: SockJSKind
    messages: tuple[str, ...] = ()
    close_code: int | None = None
    close_reason: str | None = None


def build_websocket_url(base_url: str, token: str) -> str:
    base = base_url.rstrip("/").replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    server = f"{secrets.randbelow(1000):03d}"
    session = secrets.token_hex(4)
    return f"{base}/{server}/{session}/websocket?authorization={quote(token, safe='')}"


def wrap(message: str) -> str:
    return json.dumps([message], separators=(",", ":"))


def parse(raw: str) -> SockJSFrame:
    if raw == "o":
        return SockJSFrame(SockJSKind.OPEN)
    if raw == "h":
        return SockJSFrame(SockJSKind.HEARTBEAT)
    if raw.startswith("a"):
        try:
            messages = json.loads(raw[1:])
        except json.JSONDecodeError as exc:
            raise ProtocolError("Invalid SockJS message array") from exc
        if not isinstance(messages, list) or not all(isinstance(item, str) for item in messages):
            raise ProtocolError("SockJS message payload must be a string array")
        return SockJSFrame(SockJSKind.MESSAGE, tuple(messages))
    if raw.startswith("c"):
        try:
            close = json.loads(raw[1:])
        except json.JSONDecodeError as exc:
            raise ProtocolError("Invalid SockJS close frame") from exc
        if not isinstance(close, list) or len(close) != 2:
            raise ProtocolError("SockJS close frame must contain code and reason")
        return SockJSFrame(SockJSKind.CLOSE, close_code=int(close[0]), close_reason=str(close[1]))
    raise ProtocolError("Unknown SockJS frame")
