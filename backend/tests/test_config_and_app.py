import importlib
import os
from contextlib import asynccontextmanager


def test_settings_defaults_and_cache():
    os.environ["DEBUG"] = "true"
    config = importlib.import_module("app.config")
    importlib.reload(config)
    settings = config.get_settings()
    second = config.get_settings()

    assert settings is second
    assert settings.app_name == "MedMemory API"
    assert settings.api_prefix == "/api/v1"
    assert settings.startup_require_embeddings is True


def test_blank_optional_speech_paths_normalize_to_none(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://medmemory:medmemory_dev@localhost:5432/medmemory",
    )
    monkeypatch.setenv("SPEECH_TRANSCRIPTION_LM_PATH", "")
    monkeypatch.setenv("SPEECH_SYNTHESIS_SERVICE_BASE_URL", "")

    config = importlib.import_module("app.config")
    importlib.reload(config)
    settings = config.Settings()

    assert settings.speech_transcription_lm_path is None
    assert settings.speech_synthesis_service_base_url is None


def test_main_app_metadata(monkeypatch):
    import sys
    import types

    db_mod = types.ModuleType("app.database")

    async def init_db():
        return None

    async def close_db():
        return None

    @asynccontextmanager
    async def get_db_context():
        yield None

    db_mod.init_db = init_db
    db_mod.close_db = close_db
    db_mod.get_db_context = get_db_context
    monkeypatch.setitem(sys.modules, "app.database", db_mod)

    os.environ["DEBUG"] = "true"
    config = importlib.import_module("app.config")
    importlib.reload(config)

    from app.main import app

    assert app.title == config.settings.app_name
    assert app.version == config.settings.app_version
    assert app.docs_url == "/docs"
