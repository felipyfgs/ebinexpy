import asyncio
import stat
from datetime import UTC, datetime, timedelta

import pytest

from ebinexpy.auth import FileSessionStore, MemorySessionStore, Session


@pytest.mark.asyncio
async def test_memory_store_is_identity_scoped() -> None:
    store = MemorySessionStore()
    session = Session("one", "token")
    await store.save("one", session)
    assert await store.load("one") == session
    assert await store.load("two") is None


@pytest.mark.asyncio
async def test_file_store_roundtrip_permissions_and_delete(tmp_path) -> None:
    store = FileSessionStore(tmp_path / "sessions")
    session = Session("identity", "token", "account", datetime.now(UTC) + timedelta(hours=1))
    await store.save("identity", session)

    assert await store.load("identity") == session
    path = next((tmp_path / "sessions").glob("*.json"))
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    await store.delete("identity")
    assert await store.load("identity") is None


@pytest.mark.asyncio
async def test_file_store_rejects_corrupt_and_wrong_identity(tmp_path) -> None:
    store = FileSessionStore(tmp_path)
    path = store._path("one")  # noqa: SLF001
    path.write_text("not json")
    assert await store.load("one") is None

    await store.save("one", Session("one", "token"))
    assert await store.load("two") is None


@pytest.mark.asyncio
async def test_file_store_serializes_concurrent_saves(tmp_path) -> None:
    store = FileSessionStore(tmp_path)
    await asyncio.gather(
        *(store.save("identity", Session("identity", f"token-{index}")) for index in range(20))
    )
    restored = await store.load("identity")
    assert restored is not None
    assert restored.access_token.startswith("token-")


@pytest.mark.asyncio
async def test_file_store_is_atomic_across_instances(tmp_path) -> None:
    def save(index: int) -> None:
        asyncio.run(
            FileSessionStore(tmp_path).save("identity", Session("identity", f"token-{index}"))
        )

    await asyncio.gather(*(asyncio.to_thread(save, index) for index in range(40)))

    restored = await FileSessionStore(tmp_path).load("identity")
    assert restored is not None
    assert restored.access_token.startswith("token-")
    assert not list(tmp_path.glob(".*.tmp"))


def test_session_validates_identity_and_expiry() -> None:
    assert Session("one", "token").is_valid("one")
    assert not Session("one", "token").is_valid("two")
    expired = Session("one", "token", expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert not expired.is_valid("one")
