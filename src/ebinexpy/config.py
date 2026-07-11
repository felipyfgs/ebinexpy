"""Client configuration."""

from dataclasses import dataclass, field
from pathlib import Path

from .accounts.models import AccountEnvironment
from .auth.store import MemorySessionStore, SessionStore


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Configuration shared by every ebinexpy feature."""

    environment: AccountEnvironment = AccountEnvironment.TEST
    allow_real_trading: bool = False
    http_base_url: str = "https://api.ebinex.com"
    websocket_base_url: str = "https://ws.ebinex.com/ws"
    request_timeout: float = 15.0
    connect_timeout: float = 15.0
    settlement_timeout: float = 35.0
    heartbeat_interval: float = 5.0
    reconnect_attempts: int = 5
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    reconnect_jitter: float = 0.2
    event_queue_size: int = 256
    session_store: SessionStore = field(default_factory=MemorySessionStore)

    def __post_init__(self) -> None:
        positive_fields = (
            "request_timeout",
            "connect_timeout",
            "settlement_timeout",
            "heartbeat_interval",
        )
        for name in positive_fields:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.reconnect_attempts < 0:
            raise ValueError("reconnect_attempts must be non-negative")
        if not 0 <= self.reconnect_jitter <= 1:
            raise ValueError("reconnect_jitter must be between 0 and 1")
        if self.event_queue_size <= 0:
            raise ValueError("event_queue_size must be positive")
        if not self.http_base_url.startswith("https://"):
            raise ValueError("http_base_url must use HTTPS")
        if not self.websocket_base_url.startswith("https://"):
            raise ValueError("websocket_base_url must use HTTPS")

    @classmethod
    def with_file_sessions(cls, directory: Path, **kwargs: object) -> "ClientConfig":
        from .auth.store import FileSessionStore

        return cls(session_store=FileSessionStore(directory), **kwargs)  # type: ignore[arg-type]
