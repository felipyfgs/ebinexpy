"""Assets and market-data feature."""

from .models import Asset, BookUpdate, BrokerTime, Candle, MarketStatus, Ticker, Timeframe


def __getattr__(name: str) -> object:
    if name == "MarketService":
        from .service import MarketService

        return MarketService
    raise AttributeError(name)


__all__ = [
    "Asset",
    "BookUpdate",
    "BrokerTime",
    "Candle",
    "MarketService",
    "MarketStatus",
    "Ticker",
    "Timeframe",
]
