"""Candle range, pagination and normalization helpers."""

from datetime import UTC, datetime

from ..core.exceptions import ValidationError
from .models import Timeframe

TIMEFRAME_MILLISECONDS = {Timeframe.M1: 60_000, Timeframe.M5: 300_000, Timeframe.M15: 900_000}


def milliseconds(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValidationError("Candle range datetimes must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() * 1000)
