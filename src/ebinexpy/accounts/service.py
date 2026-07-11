"""Account feature service."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ..core.exceptions import ValidationError
from ..events.models import BalanceEvent
from .models import Account, AccountEnvironment, Balance, Profile
from .wire import parse_account, parse_profile

if TYPE_CHECKING:
    from ..client import EbinexClient


class AccountService:
    """Coordinates account selection, profile and balance operations."""

    def __init__(self, client: "EbinexClient") -> None:
        self._client = client
        self.selected: Account | None = None

    async def list(self) -> list[Account]:
        response = await self._client._request("GET", "/users/listAccounts")  # noqa: SLF001
        raw = response.json()
        values = raw.get("data", raw) if isinstance(raw, dict) else raw
        return [parse_account(value) for value in values]

    async def select(self, environment: AccountEnvironment) -> Account:
        for account in await self.list():
            if account.environment is environment:
                self.selected = account
                if self._client.auth.session:
                    self._client.auth.session = replace(
                        self._client.auth.session,
                        account_id=account.id,
                    )
                await self._client._account_selected(account)  # noqa: SLF001
                return account
        raise ValidationError(f"Account environment {environment} is unavailable")

    async def profile(self) -> Profile:
        response = await self._client._request("GET", "/users")  # noqa: SLF001
        return parse_profile(response.json())

    async def balance(self) -> Balance:
        if self.selected is None:
            await self.select(self._client.config.environment)
        assert self.selected is not None
        return Balance(self.selected.balance, "USDT", self.selected)

    async def handle_event(self, destination: str, payload: object) -> None:
        if not isinstance(payload, dict) or self.selected is None:
            return
        envelope = payload.get("data", payload)
        if not isinstance(envelope, dict):
            return
        event = str(envelope.get("event") or envelope.get("type") or "").lower()
        if event != "user_balance":
            return
        from ..core.money import as_decimal

        value = envelope.get("payload", envelope)
        if not isinstance(value, dict):
            return
        account_id = str(value.get("accountId") or value.get("account_id") or "")
        if account_id and account_id != self.selected.id:
            return
        amount = as_decimal(value.get("balance", value.get("defaultCoinBalance", 0)))
        self.selected = replace(self.selected, balance=amount)
        self._client.events.emit(
            BalanceEvent(datetime.now(UTC), Balance(amount, "USDT", self.selected))
        )
