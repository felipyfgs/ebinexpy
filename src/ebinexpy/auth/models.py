"""Authentication domain models."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class Session:
    """Authenticated broker session owned by one identity."""

    identity: str
    access_token: str
    account_id: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_valid(self, identity: str, buffer: timedelta = timedelta(minutes=2)) -> bool:
        if self.identity != identity or not self.access_token:
            return False
        if self.expires_at is None:
            return True
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return datetime.now(UTC) < expiry - buffer


@dataclass(frozen=True, slots=True)
class Credentials:
    email: str
    password: str
