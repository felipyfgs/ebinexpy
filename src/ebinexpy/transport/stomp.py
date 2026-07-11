"""STOMP 1.2 framing primitives."""

from dataclasses import dataclass, field

from ..core.exceptions import ProtocolError

NULL = "\x00"


@dataclass(frozen=True, slots=True)
class StompFrame:
    command: str
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace(":", "\\c")


def _unescape(value: str) -> str:
    output = []
    index = 0
    while index < len(value):
        if value[index] != "\\":
            output.append(value[index])
            index += 1
            continue
        if index + 1 >= len(value):
            raise ProtocolError("Invalid trailing STOMP escape")
        escaped = value[index + 1]
        mapping = {"n": "\n", "r": "\r", "c": ":", "\\": "\\"}
        if escaped not in mapping:
            raise ProtocolError("Invalid STOMP escape")
        output.append(mapping[escaped])
        index += 2
    return "".join(output)


def encode(frame: StompFrame) -> str:
    headers = dict(frame.headers)
    if frame.body and "content-length" not in {key.lower() for key in headers}:
        headers["content-length"] = str(len(frame.body.encode()))
    lines = [frame.command]
    lines.extend(f"{_escape(str(key))}:{_escape(str(value))}" for key, value in headers.items())
    return "\n".join([*lines, "", frame.body]) + NULL


def decode(raw: str) -> StompFrame:
    raw = raw.rstrip(NULL)
    head, separator, body = raw.partition("\n\n")
    if not separator:
        raise ProtocolError("STOMP frame has no header/body separator")
    lines = head.splitlines()
    if not lines or not lines[0]:
        raise ProtocolError("STOMP frame has no command")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        key, separator, value = line.partition(":")
        if not separator:
            raise ProtocolError("Malformed STOMP header")
        headers[_unescape(key)] = _unescape(value)
    if "content-length" in headers:
        try:
            expected = int(headers["content-length"])
        except ValueError as exc:
            raise ProtocolError("Invalid STOMP content-length") from exc
        if len(body.encode()) != expected:
            raise ProtocolError("STOMP content-length mismatch")
    return StompFrame(lines[0], headers, body)


def connect_frame(heartbeat_ms: int) -> StompFrame:
    return StompFrame(
        "CONNECT",
        {"accept-version": "1.2,1.1,1.0", "heart-beat": f"{heartbeat_ms},{heartbeat_ms}"},
    )
