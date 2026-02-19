from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Document, Patient, PatientRelationship, User
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
    dependents_module = _load_module(
        "medmemory_dependents_api", API_DIR / "dependents.py"
    )
    app.include_router(dependents_module.router, prefix="/api/v1")
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
                Patient(
                    id=1,
                    user_id=1,
                    first_name="User",
                    last_name="One",
                    is_dependent=False,
                ),
                User(
                    id=2,
                    email="user2@example.com",
                    hashed_password="hashed",
                    full_name="User Two",
                    is_active=True,
                ),
                Patient(
                    id=2,
                    user_id=2,
                    first_name="User",
                    last_name="Two",
                    is_dependent=False,
                ),
                Patient(
                    id=3,
                    user_id=2,
                    first_name="Other",
                    last_name="Dependent",
                    is_dependent=True,
                ),
                PatientRelationship(
                    caretaker_patient_id=2,
                    dependent_patient_id=3,
                    relationship_type="child",
                    is_primary_caretaker=True,
                    can_edit=True,
                ),
                Document(
                    id=10,
                    patient_id=1,
                    filename="self.pdf",
                    original_filename="self.pdf",
                    file_path="/tmp/self.pdf",
                    file_size=12,
                    mime_type="application/pdf",
                    document_type="lab_report",
                    received_date=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    processing_status="pending",
                    is_processed=False,
                ),
                Document(
                    id=11,
                    patient_id=3,
                    filename="dep.pdf",
                    original_filename="dep.pdf",
                    file_path="/tmp/dep.pdf",
                    file_size=12,
                    mime_type="application/pdf",
                    document_type="lab_report",
                    received_date=datetime.now(UTC),
                    created_at=datetime.now(UTC),
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
async def test_dependents_crud_and_access_control(client: AsyncClient):
    create = await client.post(
        "/api/v1/dependents",
        json={
            "first_name": "Child",
            "last_name": "One",
            "date_of_birth": date(2018, 5, 1).isoformat(),
            "relationship_type": "child",
        },
    )
    assert create.status_code == 201
    created = create.json()
    dep_id = created["id"]

    listed = await client.get("/api/v1/dependents")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = await client.get(f"/api/v1/dependents/{dep_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == dep_id

    updated = await client.put(
        f"/api/v1/dependents/{dep_id}",
        json={"blood_type": "O-"},
    )
    assert updated.status_code == 200
    assert updated.json()["blood_type"] == "O-"

    deleted = await client.delete(f"/api/v1/dependents/{dep_id}")
    assert deleted.status_code == 204

    other_user_fetch = await client.get("/api/v1/dependents/3")
    assert other_user_fetch.status_code == 404


@pytest.mark.anyio
async def test_family_overview_contains_primary_and_dependents(client: AsyncClient):
    overview = await client.get("/api/v1/dependents/family/overview")
    assert overview.status_code == 200
    payload = overview.json()
    assert payload["members"]
    self_member = next(
        (m for m in payload["members"] if m["relationship_type"] is None), None
    )
    assert self_member is not None
    assert self_member["document_count"] == 1
