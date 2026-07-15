from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.speech.storage import SpeechStorageService
from app.services.speech.synthesize import SpeechSynthesisService


@pytest.mark.anyio
async def test_synthesize_uses_cached_asset_without_loading_model(tmp_path, monkeypatch):
    storage = SpeechStorageService(assets_root=tmp_path)
    service = SpeechSynthesisService(storage=storage)
    asset_id = service._build_asset_id(
        patient_id=5,
        output_language="sw",
        text="Habari yako?",
        model_name=service.model_name,
    )
    await storage.save_generated_audio(
        asset_id=asset_id,
        relative_path=asset_id,
        audio_bytes=b"RIFFdemo",
        duration_ms=910,
        metadata={"patient_id": 5},
    )

    async def fail_get_runtime():
        raise AssertionError("runtime should not load when asset is cached")

    monkeypatch.setattr(service, "_get_runtime", fail_get_runtime)

    result = await service.synthesize(
        text="Habari yako?",
        output_language="sw",
        response_mode="speech",
        patient_id=5,
        conversation_id=None,
        message_id=4,
    )

    assert result.audio_asset_id == asset_id
    assert result.audio_duration_ms == 910
    assert result.audio_url and result.audio_url.endswith(asset_id)


@pytest.mark.anyio
async def test_synthesize_generates_and_persists_audio(tmp_path, monkeypatch):
    storage = SpeechStorageService(assets_root=tmp_path)
    service = SpeechSynthesisService(storage=storage)

    async def fake_get_runtime():
        service._runtime = SimpleNamespace(sampling_rate=16000)
        return service._runtime

    monkeypatch.setattr(service, "_get_runtime", fake_get_runtime)
    monkeypatch.setattr(
        service,
        "_run_synthesis",
        lambda *, text: (b"RIFFgenerated", 1260),
    )

    result = await service.synthesize(
        text="Majibu yako yako tayari.",
        output_language="sw",
        response_mode="both",
        patient_id=9,
        conversation_id=None,
        message_id=8,
    )

    descriptor = await storage.read_generated_audio(asset_id=result.audio_asset_id)

    assert descriptor.absolute_path == Path(tmp_path / result.audio_asset_id)
    assert descriptor.metadata["patient_id"] == 9
    assert descriptor.metadata["message_id"] == 8
    assert result.audio_duration_ms == 1260
    assert result.model_name == service.model_name
