from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Document, Patient, User
from app.utils.cache import clear_cache

APP_DIR = Path(__file__).resolve().parents[1] / "app"
API_DIR = APP_DIR / "api"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@asynccontextmanager
async def _no_lifespan(_app: FastAPI):
    yield


@pytest.fixture(scope="session")
def database_url():
    pytest.importorskip("pgvector.sqlalchemy")
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for DB tests")
    return url


def _load_base():
    from app.models import Base

    return Base


def _load_database():
    from app import database

    return database


@pytest.fixture(scope="session")
async def async_engine(database_url: str):
    Base = _load_base()
    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def async_session_maker(async_engine):
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest.fixture(autouse=True)
async def clear_tables(async_engine):
    Base = _load_base()
    async with async_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await clear_cache()
    yield


@pytest.fixture()
async def client(async_session_maker):
    app = FastAPI(lifespan=_no_lifespan)
    documents_module = _load_module(
        "medmemory_documents_api_access", API_DIR / "documents.py"
    )
    app.include_router(documents_module.router, prefix="/api/v1")
    database = _load_database()
    from app.api.deps import get_authenticated_user

    async def _override_get_db():
        async with async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[database.get_db] = _override_get_db

    async with async_session_maker() as session:
        session.add_all(
            [
                User(
                    id=1,
                    email="user1@example.com",
                    hashed_password="hashed",
                    full_name="User One",
                    is_active=True,
                ),
                User(
                    id=2,
                    email="user2@example.com",
                    hashed_password="hashed",
                    full_name="User Two",
                    is_active=True,
                ),
                Patient(id=1, user_id=1, first_name="User", last_name="One"),
                Patient(id=2, user_id=2, first_name="User", last_name="Two"),
                Document(
                    id=200,
                    patient_id=2,
                    filename="other.pdf",
                    original_filename="other.pdf",
                    file_path="/tmp/other.pdf",
                    file_size=12,
                    mime_type="application/pdf",
                    document_type="lab_report",
                    received_date=datetime.now(UTC),
                    processing_status="pending",
                    is_processed=False,
                ),
            ]
        )
        await session.commit()

    async def _override_get_authenticated_user():
        return User(
            id=1,
            email="user1@example.com",
            hashed_password="hashed",
            full_name="User One",
            is_active=True,
        )

    app.dependency_overrides[get_authenticated_user] = _override_get_authenticated_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_documents_list_filters_by_owner(client: AsyncClient):
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_get_document_denies_other_users_document(client: AsyncClient):
    response = await client.get("/api/v1/documents/200")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_patient_documents_denies_other_users_patient(client: AsyncClient):
    response = await client.get("/api/v1/documents/patient/2")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_list_with_patient_filter_denies_other_user_patient(client: AsyncClient):
    response = await client.get("/api/v1/documents?patient_id=2")
    assert response.status_code == 404
