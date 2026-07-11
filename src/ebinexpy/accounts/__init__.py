"""Account, profile and balance feature."""

from .models import Account, AccountEnvironment, Balance, Profile


def __getattr__(name: str) -> object:
    if name == "AccountService":
        from .service import AccountService

        return AccountService
    raise AttributeError(name)


__all__ = ["Account", "AccountEnvironment", "AccountService", "Balance", "Profile"]
