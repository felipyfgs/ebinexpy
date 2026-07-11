"""Private account wire shapes and parsers."""

from typing import Any

from ..core.money import as_decimal
from .models import Account, AccountEnvironment, Profile


def parse_account(value: dict[str, Any]) -> Account:
    environment = AccountEnvironment(str(value.get("environment", "TEST")).upper())
    return Account(
        id=str(value.get("id", "")),
        environment=environment,
        label=str(value.get("label") or ""),
        balance=as_decimal(value.get("defaultCoinBalance", value.get("balance", 0))),
    )


def parse_profile(value: dict[str, Any]) -> Profile:
    return Profile(
        id=str(value.get("id") or value.get("uid") or ""),
        email=str(value.get("email") or ""),
        display_name=str(value.get("name") or value.get("displayName") or ""),
    )
