"""Decimal money normalization helpers."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .exceptions import ValidationError

Money = Decimal


def as_decimal(value: Decimal | int | float | str) -> Decimal:
    """Convert a wire/user value without inheriting binary float noise."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid decimal value: {value!r}") from exc


def quantize_money(value: Decimal | int | float | str, places: int = 2) -> Decimal:
    if places < 0:
        raise ValidationError("places must be non-negative")
    quantum = Decimal(1).scaleb(-places)
    return as_decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
