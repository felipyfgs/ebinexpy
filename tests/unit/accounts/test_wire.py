import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ebinexpy import EbinexClient
from ebinexpy.accounts import AccountEnvironment
from ebinexpy.accounts.models import Account
from ebinexpy.accounts.wire import parse_account, parse_profile
from ebinexpy.events import BalanceEvent


def test_account_and_profile_parsing() -> None:
    account = parse_account(
        {"id": "test-account", "environment": "TEST", "defaultCoinBalance": 12.34}
    )
    profile = parse_profile({"id": "user", "email": "placeholder", "name": "Trader"})
    assert account.environment is AccountEnvironment.TEST
    assert account.balance == Decimal("12.34")
    assert profile.display_name == "Trader"


@pytest.mark.asyncio
async def test_balance_event_updates_selected_account_with_decimal() -> None:
    client = EbinexClient()
    client.accounts.selected = Account("test-account", AccountEnvironment.TEST)
    received: list[BalanceEvent] = []

    def handler(event: object) -> None:
        if isinstance(event, BalanceEvent):
            received.append(event)

    client.events.add(handler)
    await client.accounts.handle_event(
        "/user/topic/TEST",
        {
            "data": {
                "event": "user_balance",
                "payload": {"accountId": "test-account", "balance": "12.345"},
            }
        },
    )
    await asyncio.sleep(0)

    assert client.accounts.selected.balance == Decimal("12.345")
    assert received[0].occurred_at <= datetime.now(UTC)
    await client.close()
