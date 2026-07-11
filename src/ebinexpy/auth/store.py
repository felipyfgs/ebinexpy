"""Pluggable session-store contracts."""

import asyncio
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Session


class SessionStore(Protocol):
    """Persistence boundary for identity-scoped sessions."""

    async def load(self, identity: str) -> Session | None: ...

    async def save(self, identity: str, session: Session) -> None: ...

    async def delete(self, identity: str) -> None: ...


class MemorySessionStore:
    """In-memory store used by default and by isolated consumers."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def load(self, identity: str) -> Session | None:
        return self._sessions.get(identity)

    async def save(self, identity: str, session: Session) -> None:
        self._sessions[identity] = session

    async def delete(self, identity: str) -> None:
        self._sessions.pop(identity, None)


class FileSessionStore:
    """Secure file store boundary; persistence arrives with the auth feature."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._lock = asyncio.Lock()

    def _path(self, identity: str) -> Path:
        digest = hashlib.sha256(identity.casefold().encode()).hexdigest()
        return self.directory / f"{digest}.json"

    async def load(self, identity: str) -> Session | None:
        path = self._path(identity)
        async with self._lock:
            try:
                data = json.loads(path.read_text())
            except FileNotFoundError:
                return None
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                return None
        if data.get("version") != 1 or data.get("identity") != identity:
            return None
        expires_at = data.get("expires_at")
        return Session(
            identity=data["identity"],
            access_token=data.get("access_token", ""),
            account_id=data.get("account_id"),
            expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
            metadata=data.get("metadata", {}),
        )

    async def save(self, identity: str, session: Session) -> None:
        if session.identity != identity:
            raise ValueError("session identity does not match store key")
        async with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.directory, 0o700)
            path = self._path(identity)
            payload = {
                "version": 1,
                "identity": identity,
                "access_token": session.access_token,
                "account_id": session.account_id,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "metadata": session.metadata,
            }
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=self.directory
            )
            temporary = Path(temporary_name)
            try:
                os.chmod(temporary, 0o600)
                with os.fdopen(descriptor, "w") as handle:
                    json.dump(payload, handle, separators=(",", ":"))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
                os.chmod(path, 0o600)
                directory_descriptor = os.open(self.directory, os.O_RDONLY)
                try:
                    os.fsync(directory_descriptor)
                finally:
                    os.close(directory_descriptor)
            finally:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    async def delete(self, identity: str) -> None:
        async with self._lock:
            self._path(identity).unlink(missing_ok=True)
