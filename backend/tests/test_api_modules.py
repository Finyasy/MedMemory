from __future__ import annotations

import importlib.util
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import User
from app.schemas.chat import ChatRequest
from app.schemas.ingestion import LabResultIngest
from app.schemas.memory import IndexTextRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "app" / "api"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_database_stub():
    if "app.database" in sys.modules:
        return

    db_mod = types.ModuleType("app.database")

    async def get_db():
        yield None

    db_mod.get_db = get_db
    sys.modules["app.database"] = db_mod


_install_database_stub()

context_api = _load_module("medmemory_context_api", API_DIR / "context.py")
documents_api = _load_module("medmemory_documents_api", API_DIR / "documents.py")
ingestion_api = _load_module("medmemory_ingestion_api", API_DIR / "ingestion.py")
memory_api = _load_module("medmemory_memory_api", API_DIR / "memory.py")
chat_api = _load_module("medmemory_chat_api", API_DIR / "chat.py")


class FakeResult:
    def __init__(self, scalar=None, scalars=None, rows=None):
        self._scalar = scalar
        self._scalars = scalars or []
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalars)

    def fetchall(self):
        return self._rows


class FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])

    async def execute(self, *_args, **_kwargs):
        return self._results.pop(0)

    async def delete(self, *_args, **_kwargs):
        return None


def _fake_user():
    return User(
        id=1,
        email="tester@example.com",
        hashed_password="hashed",
        full_name="Test User",
        is_active=True,
    )


@pytest.mark.anyio
async def test_ingestion_lab_success(monkeypatch):
    class FakeLabService:
        def __init__(self, db, user_id=None):
            self.db = db
            self.user_id = user_id

        async def ingest_single(self, data):
            return SimpleNamespace(
                id=1,
                patient_id=1,
                test_name=data["test_name"],
                test_code=None,
                category=None,
                value=None,
                numeric_value=None,
                unit=None,
                reference_range=None,
                status="normal",
                is_abnormal=False,
                collected_at=None,
                resulted_at=None,
                created_at=datetime.now(UTC),
            )

    monkeypatch.setattr(ingestion_api, "LabIngestionService", FakeLabService)

    payload = LabResultIngest(patient_id=1, test_name="CBC")
    db = FakeDB(results=[FakeResult(scalar=SimpleNamespace(id=1, user_id=1))])
    result = await ingestion_api.ingest_lab_result(
        payload, db=db, current_user=_fake_user()
    )

    assert result.test_name == "CBC"


@pytest.mark.anyio
async def test_ingestion_lab_error(monkeypatch):
    class FakeLabService:
        def __init__(self, db, user_id=None):
            self.db = db
            self.user_id = user_id

        async def ingest_single(self, data):
            raise ValueError("bad input")

    monkeypatch.setattr(ingestion_api, "LabIngestionService", FakeLabService)

    payload = LabResultIngest(patient_id=1, test_name="CBC")
    with pytest.raises(HTTPException) as exc:
        db = FakeDB(results=[FakeResult(scalar=SimpleNamespace(id=1, user_id=1))])
        await ingestion_api.ingest_lab_result(payload, db=db, current_user=_fake_user())

    assert exc.value.status_code == 400


@pytest.mark.anyio
async def test_memory_index_text(monkeypatch):
    class FakeIndexingService:
        def __init__(self, db):
            self.db = db

        async def index_text(self, **_kwargs):
            return [1, 2]

    monkeypatch.setattr(memory_api, "MemoryIndexingService", FakeIndexingService)

    request = IndexTextRequest(patient_id=1, content="hello")
    db = FakeDB(results=[FakeResult(scalar=SimpleNamespace(id=1, user_id=1))])
    response = await memory_api.index_custom_text(
        request, db=db, current_user=_fake_user()
    )

    assert response.total_chunks == 2


@pytest.mark.anyio
async def test_memory_search_patient_missing():
    db = FakeDB(results=[FakeResult(scalar=None)])
    with pytest.raises(HTTPException) as exc:
        await memory_api.search_patient_history(
            1,
            query="x",
            limit=10,
            min_similarity=0.3,
            db=db,
            current_user=_fake_user(),
        )

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_memory_embedding_info(monkeypatch):
    class FakeEmbedding:
        model_name = "fake"
        dimension = 3
        device = "cpu"

    monkeypatch.setattr(
        memory_api.EmbeddingService, "get_instance", lambda: FakeEmbedding()
    )

    info = await memory_api.get_embedding_info()

    assert info["model_name"] == "fake"
    assert info["dimension"] == 3


@pytest.mark.anyio
async def test_context_analyze_query(monkeypatch):
    class FakeEngine:
        def __init__(self, db):
            self.db = db

        async def analyze_query(self, query):
            return SimpleNamespace(
                original_query=query,
                normalized_query=query.lower(),
                intent=SimpleNamespace(value="general"),
                confidence=0.5,
                medical_entities=[],
                medication_names=[],
                test_names=[],
                condition_names=[],
                temporal=SimpleNamespace(
                    is_temporal=False,
                    time_range=None,
                    date_from=None,
                    date_to=None,
                    relative_days=None,
                ),
                data_sources=[],
                keywords=[],
                use_semantic_search=True,
                use_keyword_search=False,
                boost_recent=False,
            )

    monkeypatch.setattr(context_api, "ContextEngine", FakeEngine)

    response = await context_api.analyze_query(
        query="Hello", db=FakeDB(), current_user=_fake_user()
    )

    assert response.intent == "general"


@pytest.mark.anyio
async def test_chat_ask_patient_missing():
    db = FakeDB(results=[FakeResult(scalar=None)])
    payload = ChatRequest(question="Q", patient_id=1)

    with pytest.raises(HTTPException) as exc:
        await chat_api.ask_question(payload, db=db, current_user=_fake_user())

    assert exc.value.status_code == 404


@pytest.mark.anyio
async def test_chat_llm_info(monkeypatch):
    class FakeLLM:
        def get_model_info(self):
            return {
                "model_name": "fake",
                "device": "cpu",
                "max_new_tokens": 10,
                "temperature": 0.1,
                "do_sample": False,
                "top_p": 0.8,
                "top_k": 40,
                "repetition_penalty": 1.1,
                "vocab_size": 100,
                "is_loaded": False,
            }

    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    response = await chat_api.get_llm_info()

    assert response.model_name == "fake"


@pytest.mark.anyio
async def test_chat_guardrail_counters(monkeypatch):
    class FakeRAG:
        @classmethod
        def get_global_guardrail_counters(cls):
            return {"structured_direct": 2, "citation_refusal": 1}

    monkeypatch.setattr(chat_api, "RAGService", FakeRAG)

    response = await chat_api.get_guardrail_counters(current_user=_fake_user())

    assert response.counters["structured_direct"] == 2
    assert response.counters["citation_refusal"] == 1
    assert response.total == 3


@pytest.mark.anyio
async def test_chat_volume_nifti(monkeypatch, tmp_path):
    import io

    import nibabel as nib
    import numpy as np
    from starlette.datastructures import UploadFile

    async def fake_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLLM:
        async def generate_with_image(self, *args, **kwargs):
            return SimpleNamespace(
                text="Volume ok",
                tokens_input=5,
                tokens_generated=7,
                total_tokens=12,
                generation_time_ms=10.0,
            )

    monkeypatch.setattr(chat_api, "get_patient_for_user", fake_patient)
    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    volume = np.random.rand(6, 6, 4).astype(np.float32)
    image = nib.Nifti1Image(volume, affine=np.eye(4))
    nifti_path = tmp_path / "test.nii.gz"
    nib.save(image, nifti_path)
    payload = nifti_path.read_bytes()

    upload = UploadFile(filename="test.nii.gz", file=io.BytesIO(payload))
    response = await chat_api.ask_with_volume(
        prompt="Summarize",
        patient_id=1,
        slices=[upload],
        sample_count=3,
        tile_size=128,
        modality="CT",
        db=FakeDB(),
        current_user=_fake_user(),
    )

    assert response.answer == "Volume ok"


@pytest.mark.anyio
async def test_chat_wsi_patches(monkeypatch):
    import io
    from types import SimpleNamespace

    from PIL import Image
    from starlette.datastructures import UploadFile

    async def fake_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLLM:
        async def generate_with_images(self, *args, **kwargs):
            return SimpleNamespace(
                text="WSI ok",
                tokens_input=5,
                tokens_generated=7,
                total_tokens=12,
                generation_time_ms=10.0,
            )

    monkeypatch.setattr(chat_api, "get_patient_for_user", fake_patient)
    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    patch_bytes = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 40, 80)).save(patch_bytes, format="PNG")
    patch_bytes.seek(0)
    uploads = [
        UploadFile(filename="patch1.png", file=io.BytesIO(patch_bytes.getvalue())),
        UploadFile(filename="patch2.png", file=io.BytesIO(patch_bytes.getvalue())),
        UploadFile(filename="patch3.png", file=io.BytesIO(patch_bytes.getvalue())),
        UploadFile(filename="patch4.png", file=io.BytesIO(patch_bytes.getvalue())),
    ]

    response = await chat_api.ask_with_wsi(
        prompt="Summarize patches",
        patient_id=1,
        patches=uploads,
        sample_count=4,
        tile_size=128,
        db=FakeDB(),
        current_user=_fake_user(),
    )

    assert response.answer == "WSI ok"


@pytest.mark.anyio
async def test_chat_cxr_compare(monkeypatch):
    import io
    from types import SimpleNamespace

    from PIL import Image
    from starlette.datastructures import Headers, UploadFile

    async def fake_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLLM:
        async def generate_with_images(self, *args, **kwargs):
            return SimpleNamespace(
                text="CXR ok",
                tokens_input=3,
                tokens_generated=5,
                total_tokens=8,
                generation_time_ms=9.0,
            )

    monkeypatch.setattr(chat_api, "get_patient_for_user", fake_patient)
    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    img_bytes = io.BytesIO()
    Image.new("RGB", (16, 16), color=(20, 20, 20)).save(img_bytes, format="PNG")
    img_bytes.seek(0)

    headers = Headers({"content-type": "image/png"})
    current = UploadFile(
        filename="current.png", file=io.BytesIO(img_bytes.getvalue()), headers=headers
    )
    prior = UploadFile(
        filename="prior.png", file=io.BytesIO(img_bytes.getvalue()), headers=headers
    )

    response = await chat_api.compare_cxr(
        prompt="Compare",
        patient_id=1,
        current_image=current,
        prior_image=prior,
        db=FakeDB(),
        current_user=_fake_user(),
    )

    assert response.answer == "CXR ok"


@pytest.mark.anyio
async def test_localize_findings(monkeypatch):
    import io
    from types import SimpleNamespace

    from PIL import Image
    from starlette.datastructures import Headers, UploadFile

    async def fake_patient(*_args, **_kwargs):
        return SimpleNamespace(id=1, user_id=1)

    class FakeLLM:
        async def generate_with_image(self, *args, **kwargs):
            return SimpleNamespace(
                text='{"summary":"ok","boxes":[{"label":"nodule","confidence":0.82,"x_min":0.1,"y_min":0.2,"x_max":0.4,"y_max":0.5}]}',
                tokens_input=3,
                tokens_generated=5,
                total_tokens=8,
                generation_time_ms=9.0,
            )

    monkeypatch.setattr(chat_api, "get_patient_for_user", fake_patient)
    monkeypatch.setattr(chat_api.LLMService, "get_instance", lambda: FakeLLM())

    img_bytes = io.BytesIO()
    Image.new("RGB", (100, 200), color=(20, 20, 20)).save(img_bytes, format="PNG")
    img_bytes.seek(0)
    headers = Headers({"content-type": "image/png"})
    upload = UploadFile(
        filename="cxr.png", file=io.BytesIO(img_bytes.getvalue()), headers=headers
    )

    response = await chat_api.localize_findings(
        prompt="Localize",
        patient_id=1,
        image=upload,
        slices=None,
        patches=None,
        sample_count=9,
        tile_size=256,
        modality="cxr",
        db=FakeDB(),
        current_user=_fake_user(),
    )

    assert response.image_width == 100
    assert response.image_height == 200
    assert response.boxes[0].x_min == 10
    assert response.boxes[0].y_max == 100


@pytest.mark.anyio
async def test_documents_list_and_text_error():
    document = SimpleNamespace(
        id=1,
        patient_id=1,
        filename="file.txt",
        original_filename="file.txt",
        file_size=10,
        mime_type="text/plain",
        document_type="note",
        category=None,
        title=None,
        description=None,
        document_date=None,
        received_date=datetime.now(UTC),
        processing_status="pending",
        is_processed=False,
        processed_at=None,
        page_count=None,
        created_at=datetime.now(UTC),
    )

    db = FakeDB(results=[FakeResult(scalars=[document])])
    listed = await documents_api.list_documents(
        db=db, skip=0, limit=100, current_user=_fake_user()
    )

    assert len(listed) == 1

    db = FakeDB(results=[FakeResult(scalar=document)])
    with pytest.raises(HTTPException) as exc:
        await documents_api.get_document_text(1, db=db, current_user=_fake_user())

    assert exc.value.status_code == 400


def test_api_init_exports():
    module = _load_module("medmemory_api_init", API_DIR / "__init__.py")

    assert "health" in module.__all__
    assert "ingestion" in module.__all__
