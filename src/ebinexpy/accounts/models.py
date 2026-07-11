"""Account domain models."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AccountEnvironment(StrEnum):
    TEST = "TEST"
    REAL = "REAL"
    SPOT = "SPOT"


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    environment: AccountEnvironment
    label: str = ""
    balance: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class Balance:
    amount: Decimal
    currency: str
    account: Account


@dataclass(frozen=True, slots=True)
class Profile:
    id: str
    email: str
    display_name: str = ""
