"""Secret-redaction and logging configuration."""

import json
import logging
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "<redacted>"
_SENSITIVE_KEY = re.compile(
    r"authorization|cookie|password|token|secret|account_?id|user_?id|order_?id|email",
    re.IGNORECASE,
)
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_AUTH_QUERY = re.compile(r"([?&](?:authorization|token|accountid)=)[^&\s]+", re.IGNORECASE)
_BEARER = re.compile(r"Bearer\s+[^\s,;]+", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"(?<![A-Za-z0-9])(?:[a-f0-9]{24,32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def redact_text(value: str) -> str:
    value = _JWT.sub(REDACTED, value)
    value = _BEARER.sub(f"Bearer {REDACTED}", value)
    value = _AUTH_QUERY.sub(rf"\1{REDACTED}", value)
    return _IDENTIFIER.sub(REDACTED, value)


def redact(value: Any, key: str = "") -> Any:
    if key and _SENSITIVE_KEY.search(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        if record.args:
            if isinstance(record.args, Mapping):
                record.args = redact(record.args)
            else:
                record.args = tuple(redact(item) for item in record.args)
        return True


def safe_json(value: Any) -> str:
    return json.dumps(redact(value), ensure_ascii=False, default=str)
