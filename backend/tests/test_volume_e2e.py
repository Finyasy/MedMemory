from __future__ import annotations

import io
import tempfile
from types import SimpleNamespace

import numpy as np
import nibabel as nib
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api import deps as deps_module


class FakeUser:
    id = 1
    email = "tester@example.com"
    is_active = True


async def _fake_user():
    return FakeUser()


async def _fake_db():
    yield None


@pytest.mark.anyio
async def test_volume_chat_flow(monkeypatch):
    async def fake_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLLM:
        async def generate_with_image(self, *args, **kwargs):
            return SimpleNamespace(
                text="Volume response",
                tokens_input=4,
                tokens_generated=6,
                total_tokens=10,
                generation_time_ms=12.0,
            )

    from app.api import chat as chat_api
    monkeypatch.setattr(chat_api, "get_patient_for_user", fake_patient)
    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    app.dependency_overrides[deps_module.get_authenticated_user] = _fake_user
    app.dependency_overrides[deps_module.get_db] = _fake_db

    volume = np.random.rand(6, 6, 4).astype(np.float32)
    image = nib.Nifti1Image(volume, affine=np.eye(4))
    with tempfile.NamedTemporaryFile(suffix=".nii.gz") as tmp:
        nib.save(image, tmp.name)
        payload = tmp.read()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"slices": ("volume.nii.gz", io.BytesIO(payload), "application/gzip")}
        data = {
            "prompt": "Summarize",
            "patient_id": "1",
            "sample_count": "3",
            "tile_size": "128",
            "modality": "CT",
        }
        response = await client.post("/api/v1/chat/volume", data=data, files=files)

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Volume response"
