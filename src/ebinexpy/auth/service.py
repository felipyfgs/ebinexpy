"""Authentication feature service."""

from typing import TYPE_CHECKING

from ..core.exceptions import AuthenticationError
from .models import Credentials, Session
from .wire import parse_login

if TYPE_CHECKING:
    from ..client import EbinexClient


class AuthService:
    """Coordinates login, session restore and logout."""

    def __init__(self, client: "EbinexClient") -> None:
        self._client = client
        self.session: Session | None = None

    @property
    def authenticated(self) -> bool:
        return self.session is not None

    async def ensure(self, credentials: Credentials) -> Session:
        store = self._client.config.session_store
        cached = await store.load(credentials.email)
        if cached and cached.is_valid(credentials.email):
            self.session = cached
            return cached
        if not credentials.email or not credentials.password:
            raise AuthenticationError("Email and password are required")
        response = await self._client._http.request(  # noqa: SLF001
            "POST",
            "/auth/login",
            json={
                "email": credentials.email,
                "password": credentials.password,
                "keepLoggedIn": True,
                "captchaCode": "CAPTCHA_DISABLED",
            },
        )
        session = parse_login(response, credentials.email, self._client.config.environment.value)
        await store.save(credentials.email, session)
        self.session = session
        return session

    async def logout(self, identity: str) -> None:
        if self.session is not None and self.session.identity == identity:
            self.session = None
        await self._client.config.session_store.delete(identity)
