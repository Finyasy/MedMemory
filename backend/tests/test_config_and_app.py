from app import config


def test_settings_defaults_and_cache():
    settings = config.get_settings()
    second = config.get_settings()

    assert settings is second
    assert settings.app_name == "MedMemory API"
    assert settings.api_prefix == "/api/v1"


def test_main_app_metadata():
    import sys
    import types

    db_mod = sys.modules.get("app.database") or types.ModuleType("app.database")

    async def init_db():
        return None

    async def close_db():
        return None

    db_mod.init_db = init_db
    db_mod.close_db = close_db
    sys.modules["app.database"] = db_mod

    from app.main import app

    assert app.title == config.settings.app_name
    assert app.version == config.settings.app_version
    assert app.docs_url == "/docs"
