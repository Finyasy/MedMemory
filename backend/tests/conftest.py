from contextlib import asynccontextmanager
import importlib.metadata
import importlib.util
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.types import TypeEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

API_DIR = PROJECT_ROOT / "app" / "api"



def _install_pgvector_stub():
    try:
        import pgvector.sqlalchemy  # noqa: F401
        return
    except Exception:
        pass

    pgvector_pkg = types.ModuleType("pgvector")
    sqlalchemy_mod = types.ModuleType("pgvector.sqlalchemy")

    class Vector(TypeEngine):
        cache_ok = True

        def __init__(self, *_args, **_kwargs):
            super().__init__()

    sqlalchemy_mod.Vector = Vector
    pgvector_pkg.sqlalchemy = sqlalchemy_mod
    sys.modules["pgvector"] = pgvector_pkg
    sys.modules["pgvector.sqlalchemy"] = sqlalchemy_mod


def _install_email_validator_stub():
    try:
        import email_validator  # noqa: F401
        return
    except Exception:
        pass

    original_version = importlib.metadata.version

    def _version(name: str):
        if name == "email-validator":
            return "2.0.0"
        return original_version(name)

    importlib.metadata.version = _version

    email_mod = types.ModuleType("email_validator")

    class EmailNotValidError(Exception):
        pass

    def validate_email(email, **_kwargs):
        if "@" not in email:
            raise EmailNotValidError("invalid email")
        return types.SimpleNamespace(email=email)

    email_mod.EmailNotValidError = EmailNotValidError
    email_mod.validate_email = validate_email
    sys.modules["email_validator"] = email_mod


def _disable_pydantic_email_validator():
    try:
        import pydantic.networks as networks
        networks.import_email_validator = lambda: None
    except Exception:
        pass


def _install_asyncpg_stub():
    try:
        import asyncpg  # noqa: F401
        return
    except Exception:
        pass

    asyncpg_mod = types.ModuleType("asyncpg")

    async def connect(*_args, **_kwargs):
        raise RuntimeError("asyncpg stub: connection not available in tests")

    class AsyncpgError(Exception):
        pass

    asyncpg_mod.connect = connect
    asyncpg_mod.PostgresError = AsyncpgError
    asyncpg_mod.__all__ = ["connect", "PostgresError"]
    sys.modules["asyncpg"] = asyncpg_mod


def _install_fitz_stub():
    try:
        import fitz  # noqa: F401
        return
    except Exception:
        pass

    fitz_mod = types.ModuleType("fitz")

    def _stub_open(*_args, **_kwargs):
        raise RuntimeError("fitz stub: PDF operations not available in tests")

    class Page:
        pass

    class Document:
        pass

    fitz_mod.open = _stub_open
    fitz_mod.Page = Page
    fitz_mod.Document = Document
    sys.modules["fitz"] = fitz_mod


def _install_multipart_stub():
    try:
        import multipart  # noqa: F401
        return
    except Exception:
        pass

    multipart_pkg = types.ModuleType("multipart")
    multipart_pkg.__version__ = "0.0.0"

    multipart_sub = types.ModuleType("multipart.multipart")

    def parse_options_header(value):
        return value, {}

    multipart_sub.parse_options_header = parse_options_header

    sys.modules["multipart"] = multipart_pkg
    sys.modules["multipart.multipart"] = multipart_sub


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_install_pgvector_stub()
_install_email_validator_stub()
_disable_pydantic_email_validator()
_install_asyncpg_stub()
_install_fitz_stub()
_install_multipart_stub()

collect_ignore = ["test_model.py"]


@pytest.fixture
def anyio_backend():
    return "asyncio"

HEALTH_MODULE = _load_module("medmemory_health_api", API_DIR / "health.py")
RECORDS_MODULE = _load_module("medmemory_records_api", API_DIR / "records.py")


@asynccontextmanager
async def _no_lifespan(app):
    yield


@pytest.fixture()
def client(record_repository):
    app = FastAPI(lifespan=_no_lifespan)
    app.include_router(HEALTH_MODULE.router)
    app.include_router(RECORDS_MODULE.router, prefix="/api/v1")
    
    app.dependency_overrides[RECORDS_MODULE.get_record_repo] = lambda: record_repository
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def records_module():
    return RECORDS_MODULE


@pytest.fixture()
def record_repository():
    from app.services.records import InMemoryRecordRepository

    return InMemoryRecordRepository()
