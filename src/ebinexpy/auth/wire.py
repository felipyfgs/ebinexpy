"""Private authentication wire shapes and parsers."""

import base64
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from ..core.exceptions import AuthenticationError
from .models import Session

ACCESS_COOKIE = "ebinex:accessToken"
ACCOUNT_COOKIE = "ebinex:accountId"


def jwt_expiry(token: str) -> datetime | None:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        value = json.loads(base64.urlsafe_b64decode(payload))
        return datetime.fromtimestamp(float(value["exp"]), tz=UTC)
    except (IndexError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


def parse_login(response: httpx.Response, identity: str, environment: str = "TEST") -> Session:
    try:
        body: dict[str, Any] = response.json()
    except (json.JSONDecodeError, TypeError):
        body = {}
    token = response.cookies.get(ACCESS_COOKIE) or body.get("token") or body.get("accessToken")
    if not token:
        raise AuthenticationError("Login response did not include an access token")
    account_id = response.cookies.get(ACCOUNT_COOKIE) or body.get("accountId")
    accounts = body.get("accounts", [])
    if not account_id and isinstance(accounts, list):
        selected = next(
            (
                value
                for value in accounts
                if isinstance(value, dict)
                and str(value.get("environment", "")).upper() == environment.upper()
            ),
            None,
        )
        if selected:
            account_id = selected.get("id")
    return Session(
        identity,
        str(token),
        str(account_id) if account_id else None,
        jwt_expiry(str(token)),
        body,
    )
