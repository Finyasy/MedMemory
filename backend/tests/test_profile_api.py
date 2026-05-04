from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Patient, User
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
    profile_module = _load_module("medmemory_profile_api", API_DIR / "profile.py")
    app.include_router(profile_module.router, prefix="/api/v1")
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
                Patient(
                    id=1,
                    user_id=1,
                    first_name="User",
                    last_name="One",
                    is_dependent=False,
                ),
                Patient(
                    id=2,
                    user_id=2,
                    first_name="User",
                    last_name="Two",
                    is_dependent=False,
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
async def test_get_profile_default_patient(client: AsyncClient):
    response = await client.get("/api/v1/profile")
    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "User One"
    assert payload["profile_completion"]["overall_percentage"] >= 0


@pytest.mark.anyio
async def test_update_basic_profile(client: AsyncClient):
    update = {
        "date_of_birth": date(1990, 1, 2).isoformat(),
        "sex": "female",
        "blood_type": "O+",
        "height_cm": 170.5,
        "weight_kg": 65.2,
    }
    response = await client.put("/api/v1/profile/basic", json=update)
    assert response.status_code == 200
    payload = response.json()
    assert payload["blood_type"] == "O+"
    assert payload["sex"] == "female"


@pytest.mark.anyio
async def test_update_emergency_info(client: AsyncClient):
    response = await client.put(
        "/api/v1/profile/emergency",
        json={"medical_alert": "Asthma", "organ_donor": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["medical_alert"] == "Asthma"
    assert payload["organ_donor"] is True


@pytest.mark.anyio
async def test_emergency_contact_crud(client: AsyncClient):
    create = await client.post(
        "/api/v1/profile/emergency-contacts",
        json={
            "name": "Jane Doe",
            "relationship": "spouse",
            "phone": "555-0101",
            "is_primary": True,
        },
    )
    assert create.status_code == 201
    contact = create.json()
    contact_id = contact["id"]

    listed = await client.get("/api/v1/profile/emergency-contacts")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await client.put(
        f"/api/v1/profile/emergency-contacts/{contact_id}",
        json={"phone": "555-0202"},
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "555-0202"

    deleted = await client.delete(f"/api/v1/profile/emergency-contacts/{contact_id}")
    assert deleted.status_code == 204


@pytest.mark.anyio
async def test_allergy_crud(client: AsyncClient):
    create = await client.post(
        "/api/v1/profile/allergies",
        json={
            "allergen": "Peanuts",
            "allergy_type": "food",
            "severity": "high",
        },
    )
    assert create.status_code == 201
    allergy = create.json()
    allergy_id = allergy["id"]

    listed = await client.get("/api/v1/profile/allergies")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = await client.put(
        f"/api/v1/profile/allergies/{allergy_id}",
        json={"reaction": "Hives"},
    )
    assert updated.status_code == 200
    assert updated.json()["reaction"] == "Hives"

    deleted = await client.delete(f"/api/v1/profile/allergies/{allergy_id}")
    assert deleted.status_code == 204


@pytest.mark.anyio
async def test_lifestyle_create_and_update(client: AsyncClient):
    create = await client.put(
        "/api/v1/profile/lifestyle",
        json={"smoking_status": "never", "sleep_hours": 7.5},
    )
    assert create.status_code == 200
    payload = create.json()
    assert payload["smoking_status"] == "never"

    update = await client.put(
        "/api/v1/profile/lifestyle",
        json={"exercise_frequency": "weekly"},
    )
    assert update.status_code == 200
    assert update.json()["exercise_frequency"] == "weekly"


@pytest.mark.anyio
async def test_profile_access_control_patient_id(client: AsyncClient):
    response = await client.get("/api/v1/profile?patient_id=2")
    assert response.status_code == 404

    update = await client.put(
        "/api/v1/profile/basic?patient_id=2",
        json={"blood_type": "A-"},
    )
    assert update.status_code == 404


@pytest.mark.anyio
async def test_profile_prefers_oldest_primary_patient_when_duplicates_exist(
    client: AsyncClient,
    async_session_maker,
    caplog: pytest.LogCaptureFixture,
):
    async with async_session_maker() as session:
        session.add(
            Patient(
                id=3,
                user_id=1,
                first_name="Backup",
                last_name="Profile",
                is_dependent=False,
            )
        )
        await session.commit()

    with caplog.at_level("WARNING"):
        response = await client.get("/api/v1/profile")

    assert response.status_code == 200
    assert response.json()["id"] == 1
    assert "Multiple primary patient rows found for user_id=1" in caplog.text


def test_calculate_profile_completion_marks_completed_sections():
    profile_module = _load_module("medmemory_profile_helpers", API_DIR / "profile.py")
    patient = Patient(
        id=99,
        user_id=1,
        first_name="Test",
        last_name="Patient",
        date_of_birth=date(1992, 4, 5),
        sex="female",
        blood_type="O+",
        height_cm=165,
        weight_kg=62,
        is_dependent=False,
    )
    patient.emergency_info = object()
    patient.emergency_contacts = [object()]
    patient.allergies_list = [object()]
    patient.conditions_list = [object()]
    patient.family_history_list = [object()]
    patient.providers = [object()]
    patient.lifestyle = SimpleNamespace(
        smoking_status="never",
        alcohol_use="never",
        exercise_frequency="active",
        sleep_hours=8,
    )

    completion = profile_module.calculate_profile_completion(patient)

    assert completion.overall_percentage == 100
    assert completion.sections["basic_info"]["complete"] is True
    assert completion.sections["emergency"]["percentage"] == 100
    assert completion.sections["medical_history"]["complete"] is True
    assert completion.sections["providers"]["complete"] is True
    assert completion.sections["lifestyle"]["complete"] is True


@pytest.mark.anyio
async def test_condition_and_provider_crud(client: AsyncClient):
    lifestyle = await client.get("/api/v1/profile/lifestyle")
    assert lifestyle.status_code == 200
    assert lifestyle.json() is None

    create_condition = await client.post(
        "/api/v1/profile/conditions",
        json={
            "condition_name": "Hypertension",
            "status": "active",
            "severity": "moderate",
        },
    )
    assert create_condition.status_code == 201
    condition_id = create_condition.json()["id"]

    listed_conditions = await client.get("/api/v1/profile/conditions")
    assert listed_conditions.status_code == 200
    assert listed_conditions.json()[0]["condition_name"] == "Hypertension"

    updated_condition = await client.put(
        f"/api/v1/profile/conditions/{condition_id}",
        json={"status": "resolved", "notes": "Symptoms improved"},
    )
    assert updated_condition.status_code == 200
    assert updated_condition.json()["status"] == "resolved"

    deleted_condition = await client.delete(
        f"/api/v1/profile/conditions/{condition_id}"
    )
    assert deleted_condition.status_code == 204

    create_provider = await client.post(
        "/api/v1/profile/providers",
        json={
            "provider_type": "pcp",
            "name": "Dr. Maina",
            "clinic_name": "Westlands Clinic",
            "phone": "555-1111",
        },
    )
    assert create_provider.status_code == 201
    provider_id = create_provider.json()["id"]

    listed_providers = await client.get("/api/v1/profile/providers")
    assert listed_providers.status_code == 200
    assert listed_providers.json()[0]["name"] == "Dr. Maina"

    updated_provider = await client.put(
        f"/api/v1/profile/providers/{provider_id}",
        json={"is_primary": True, "notes": "Quarterly follow-up"},
    )
    assert updated_provider.status_code == 200
    assert updated_provider.json()["is_primary"] is True

    deleted_provider = await client.delete(f"/api/v1/profile/providers/{provider_id}")
    assert deleted_provider.status_code == 204


@pytest.mark.anyio
async def test_insurance_family_history_vaccination_and_growth_crud(client: AsyncClient):
    create_insurance = await client.post(
        "/api/v1/profile/insurance",
        json={
            "provider_name": "AAR",
            "policy_number": "POL-123",
            "subscriber_name": "User One",
        },
    )
    assert create_insurance.status_code == 201
    insurance_id = create_insurance.json()["id"]

    list_insurance = await client.get("/api/v1/profile/insurance")
    assert list_insurance.status_code == 200
    assert list_insurance.json()[0]["provider_name"] == "AAR"

    delete_insurance = await client.delete(
        f"/api/v1/profile/insurance/{insurance_id}"
    )
    assert delete_insurance.status_code == 204

    create_history = await client.post(
        "/api/v1/profile/family-history",
        json={
            "relation": "mother",
            "condition": "Diabetes",
            "age_of_onset": 52,
        },
    )
    assert create_history.status_code == 201
    history_id = create_history.json()["id"]

    list_history = await client.get("/api/v1/profile/family-history")
    assert list_history.status_code == 200
    assert list_history.json()[0]["condition"] == "Diabetes"

    delete_history = await client.delete(
        f"/api/v1/profile/family-history/{history_id}"
    )
    assert delete_history.status_code == 204

    create_vaccination = await client.post(
        "/api/v1/profile/vaccinations",
        json={
            "vaccine_name": "Influenza",
            "dose_number": 1,
            "date_administered": "2025-10-01",
        },
    )
    assert create_vaccination.status_code == 201
    vaccination_id = create_vaccination.json()["id"]

    list_vaccinations = await client.get("/api/v1/profile/vaccinations")
    assert list_vaccinations.status_code == 200
    assert list_vaccinations.json()[0]["vaccine_name"] == "Influenza"

    delete_vaccination = await client.delete(
        f"/api/v1/profile/vaccinations/{vaccination_id}"
    )
    assert delete_vaccination.status_code == 204

    create_growth = await client.post(
        "/api/v1/profile/growth",
        json={
            "measurement_date": "2026-03-01",
            "age_months": 24,
            "height_cm": 90.5,
            "weight_kg": 13.2,
        },
    )
    assert create_growth.status_code == 201
    measurement_id = create_growth.json()["id"]

    list_growth = await client.get("/api/v1/profile/growth")
    assert list_growth.status_code == 200
    assert list_growth.json()[0]["age_months"] == 24

    delete_growth = await client.delete(
        f"/api/v1/profile/growth/{measurement_id}"
    )
    assert delete_growth.status_code == 204
