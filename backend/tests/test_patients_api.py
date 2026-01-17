from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


def _expected_age(birth_date: date) -> int:
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


@pytest.fixture(scope="session")
def database_url():
    pytest.importorskip("pgvector.sqlalchemy")
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL or DATABASE_URL is required for DB tests")
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
    yield


@pytest.fixture()
async def client(async_session_maker):
    app = FastAPI(lifespan=_no_lifespan)
    patients_module = _load_module("medmemory_patients_api", API_DIR / "patients.py")
    app.include_router(patients_module.router, prefix="/api/v1")
    database = _load_database()

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

    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_and_list_patients(client: AsyncClient):
    birth_date = date(1990, 1, 2)
    payload = {
        "external_id": "ext-123",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "date_of_birth": birth_date.isoformat(),
        "gender": "female",
        "email": "ada@example.com",
    }

    create_response = await client.post("/api/v1/patients/", json=payload)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["full_name"] == "Ada Lovelace"
    assert created["age"] == _expected_age(birth_date)
    assert created["external_id"] == payload["external_id"]

    list_response = await client.get("/api/v1/patients/")

    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["full_name"] == "Ada Lovelace"


@pytest.mark.anyio
async def test_duplicate_external_id_returns_400(client: AsyncClient):
    payload = {
        "external_id": "dup-1",
        "first_name": "Alan",
        "last_name": "Turing",
    }

    first_response = await client.post("/api/v1/patients/", json=payload)
    second_response = await client.post("/api/v1/patients/", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert "already exists" in second_response.json()["detail"]


@pytest.mark.anyio
async def test_update_and_delete_patient(client: AsyncClient):
    create_response = await client.post(
        "/api/v1/patients/",
        json={"first_name": "Grace", "last_name": "Hopper"},
    )
    patient_id = create_response.json()["id"]

    update_response = await client.patch(
        f"/api/v1/patients/{patient_id}",
        json={"email": "grace.hopper@example.com"},
    )

    assert update_response.status_code == 200
    assert update_response.json()["email"] == "grace.hopper@example.com"

    delete_response = await client.delete(f"/api/v1/patients/{patient_id}")

    assert delete_response.status_code == 204

    get_response = await client.get(f"/api/v1/patients/{patient_id}")

    assert get_response.status_code == 404
