from types import SimpleNamespace

import pytest

from app import database


class _FakeConn:
    async def exec_driver_sql(self, _sql: str) -> None:
        return None

    async def run_sync(self, _fn) -> None:
        return None


class _FakeBeginFactory:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def __call__(self):
        self.calls += 1
        call_number = self.calls
        fail_times = self.fail_times

        class _Ctx:
            async def __aenter__(self_nonlocal):
                if call_number <= fail_times:
                    raise ConnectionError("db not ready")
                return _FakeConn()

            async def __aexit__(self_nonlocal, exc_type, exc, tb):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_init_db_retries_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    begin_factory = _FakeBeginFactory(fail_times=2)
    fake_engine = SimpleNamespace(begin=begin_factory)

    monkeypatch.setattr(database, "engine", fake_engine)
    monkeypatch.setattr(database.settings, "debug", False, raising=False)
    monkeypatch.setattr(database.settings, "database_init_retries", 3, raising=False)
    monkeypatch.setattr(
        database.settings,
        "database_init_retry_delay_seconds",
        0.01,
        raising=False,
    )

    async def _noop_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(database.asyncio, "sleep", _noop_sleep)

    await database.init_db()

    assert begin_factory.calls == 3


@pytest.mark.asyncio
async def test_init_db_raises_after_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    begin_factory = _FakeBeginFactory(fail_times=10)
    fake_engine = SimpleNamespace(begin=begin_factory)

    monkeypatch.setattr(database, "engine", fake_engine)
    monkeypatch.setattr(database.settings, "debug", False, raising=False)
    monkeypatch.setattr(database.settings, "database_init_retries", 1, raising=False)
    monkeypatch.setattr(
        database.settings,
        "database_init_retry_delay_seconds",
        0.01,
        raising=False,
    )

    async def _noop_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(database.asyncio, "sleep", _noop_sleep)

    with pytest.raises(ConnectionError, match="db not ready"):
        await database.init_db()

    assert begin_factory.calls == 2
