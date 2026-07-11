"""OPTION request validation and real-account safety gates."""

from ..accounts.models import AccountEnvironment
from ..core.exceptions import RealTradingDisabledError, ValidationError
from ..market.models import Asset, MarketStatus
from .models import OrderRequest


def guard_environment(environment: AccountEnvironment, allow_real: bool) -> None:
    if environment is AccountEnvironment.REAL and not allow_real:
        raise RealTradingDisabledError(
            "REAL order execution requires ClientConfig(allow_real_trading=True)"
        )


def validate_request(request: OrderRequest, asset: Asset) -> None:
    if not request.symbol.strip():
        raise ValidationError("Order symbol is required")
    if request.investment <= 0:
        raise ValidationError("Order investment must be positive")
    if asset.status is not MarketStatus.ACTIVE:
        raise ValidationError(f"{asset.symbol} OPTION market is closed")
    if request.timeframe not in asset.timeframes:
        raise ValidationError(f"{asset.symbol} does not support {request.timeframe}")
    if request.price is not None and request.price <= 0:
        raise ValidationError("Order price must be positive")
