import pytest

from ebinexpy.core.exceptions import ProtocolError
from ebinexpy.transport.sockjs import (
    SockJSKind,
    wrap,
)
from ebinexpy.transport.sockjs import (
    parse as parse_sockjs,
)
from ebinexpy.transport.stomp import StompFrame, connect_frame, decode, encode


def test_sockjs_frames() -> None:
    assert parse_sockjs("o").kind is SockJSKind.OPEN
    assert parse_sockjs("h").kind is SockJSKind.HEARTBEAT
    assert parse_sockjs('a["one","two"]').messages == ("one", "two")
    assert wrap("frame") == '["frame"]'


def test_stomp_roundtrip_and_content_length() -> None:
    original = StompFrame("MESSAGE", {"destination": "/topic/a:b"}, '{"ok":true}')
    parsed = decode(encode(original))
    assert parsed.command == original.command
    assert parsed.headers["destination"] == "/topic/a:b"
    assert parsed.headers["content-length"] == "11"
    assert parsed.body == original.body


def test_connect_heartbeat() -> None:
    assert connect_frame(5000).headers["heart-beat"] == "5000,5000"


def test_rejects_invalid_sockjs_and_stomp() -> None:
    with pytest.raises(ProtocolError):
        parse_sockjs("invalid")
    with pytest.raises(ProtocolError):
        decode("MESSAGE\nmissing")
