from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


@asynccontextmanager
async def _no_lifespan(_app: FastAPI):
    yield


def _load_app_with_no_lifespan():
    from app import main

    app = main.app
    app.router.lifespan_context = _no_lifespan
    return app


def test_security_headers_are_set():
    app = _load_app_with_no_lifespan()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert (
        response.headers.get("Permissions-Policy")
        == "geolocation=(), microphone=(), camera=()"
    )
    assert (
        response.headers.get("Content-Security-Policy")
        == "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert "X-Request-Id" in response.headers


def test_cors_middleware_present():
    app = _load_app_with_no_lifespan()
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert cors


@pytest.mark.anyio
async def test_lifespan_calls_init_and_close(monkeypatch):
    from app import main

    called = {"init": 0, "close": 0, "embed": 0}

    async def _init_db():
        called["init"] += 1

    async def _close_db():
        called["close"] += 1

    class FakeEmbeddingService:
        model = "ok"

    monkeypatch.setattr(main, "init_db", _init_db)
    monkeypatch.setattr(main, "close_db", _close_db)
    monkeypatch.setattr(
        main.EmbeddingService,
        "get_instance",
        lambda: SimpleNamespace(model=FakeEmbeddingService.model),
    )

    async with main.lifespan(FastAPI()):
        pass

    assert called["init"] == 1
    assert called["close"] == 1


@pytest.mark.anyio
async def test_lifespan_fails_fast_on_missing_embedding_dependency(monkeypatch):
    from app import main
    from app.services.embeddings import MissingMLDependencyError

    called = {"init": 0, "close": 0}

    async def _init_db():
        called["init"] += 1

    async def _close_db():
        called["close"] += 1

    class BrokenEmbeddingService:
        @property
        def model(self):
            raise MissingMLDependencyError(
                "Missing required ML dependency 'requests' while loading embeddings."
            )

    monkeypatch.setattr(main, "init_db", _init_db)
    monkeypatch.setattr(main, "close_db", _close_db)
    monkeypatch.setattr(
        main.EmbeddingService,
        "get_instance",
        lambda: BrokenEmbeddingService(),
    )

    with pytest.raises(RuntimeError, match="Missing required ML dependency 'requests'"):
        async with main.lifespan(FastAPI()):
            pass

    assert called["init"] == 1
    assert called["close"] == 0


def test_alembic_versions_have_revisions():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    files = sorted(versions_dir.glob("*.py"))
    assert files, "No alembic versions found"
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "revision" in text
        assert "down_revision" in text
