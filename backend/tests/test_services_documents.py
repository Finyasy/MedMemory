from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image

from app.services.documents.chunking import TextChunker
from app.services.documents.extraction import (
    ExtractionResult,
    ImageExtractor,
    get_extractor,
)
from app.services.documents.processor import DocumentProcessor
from app.services.documents.upload import DocumentUploadService


class DummyDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


def test_text_chunker_page_numbers():
    chunker = TextChunker(chunk_size=50, chunk_overlap=0)
    text = "--- Page 1 ---\nAlpha\n--- Page 2 ---\nBeta"
    chunks = chunker.chunk_by_pages(text)

    assert chunks
    assert {c.page_number for c in chunks} == {2, 3}


def test_extraction_result_empty_property():
    assert ExtractionResult(text="", page_count=0).is_empty is True
    assert ExtractionResult(text="content", page_count=1).is_empty is False


def test_get_extractor_by_mime_type():
    assert get_extractor("application/pdf").supports("application/pdf")
    assert get_extractor("image/png").supports("image/png")
    assert get_extractor(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert get_extractor("application/unknown") is None


@pytest.mark.anyio
async def test_image_extractor_without_tesseract():
    extractor = ImageExtractor()
    extractor._tesseract_available = False
    image = Image.new("RGB", (10, 10), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    result = await extractor.extract_from_bytes(buffer.getvalue(), "image/png")

    assert result.text == ""
    assert result.page_count == 1


@pytest.mark.anyio
async def test_document_upload_helpers_validate_and_detect():
    service = DocumentUploadService(db=DummyDB())

    file = UploadFile(filename="labs.pdf", file=BytesIO(b"content"))
    await service._validate_file(file)

    assert service._get_extension("labs.pdf") == ".pdf"
    assert (
        service._detect_document_type("lab_results.pdf", "application/pdf")
        == "lab_report"
    )
    assert service._compute_hash(b"content") == service._compute_hash(b"content")

    bad_file = UploadFile(filename="bad.exe", file=BytesIO(b"content"))
    with pytest.raises(ValueError):
        await service._validate_file(bad_file)


@pytest.mark.anyio
async def test_document_processor_creates_chunks():
    db = DummyDB()
    processor = DocumentProcessor(db, chunk_size=20, chunk_overlap=0)
    document = type(
        "Doc", (), {"patient_id": 1, "id": 2, "document_date": datetime(2024, 1, 1)}
    )()
    extraction = ExtractionResult(text="Alpha Beta Gamma Delta", page_count=1)

    chunks = await processor._create_memory_chunks(document, extraction)

    assert chunks
    assert len(db.added) == len(chunks)
