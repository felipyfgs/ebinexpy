from ebinexpy import ClientConfig, EbinexClient
from ebinexpy.accounts import AccountEnvironment, AccountService
from ebinexpy.auth import AuthService, MemorySessionStore
from ebinexpy.events import EventDispatcher
from ebinexpy.market import MarketService
from ebinexpy.orders import OrderService
from ebinexpy.raw import RawClient


def test_default_config_is_demo_and_blocks_real_trading() -> None:
    config = ClientConfig()

    assert config.environment is AccountEnvironment.TEST
    assert config.allow_real_trading is False
    assert isinstance(config.session_store, MemorySessionStore)


def test_client_composes_feature_services() -> None:
    client = EbinexClient()

    assert isinstance(client.auth, AuthService)
    assert isinstance(client.accounts, AccountService)
    assert isinstance(client.market, MarketService)
    assert isinstance(client.orders, OrderService)
    assert isinstance(client.events, EventDispatcher)
    assert isinstance(client.raw, RawClient)
