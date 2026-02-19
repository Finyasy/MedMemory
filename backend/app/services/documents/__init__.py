"""Document processing services for MedMemory."""

from importlib import import_module

__all__ = [
    "DocumentUploadService",
    "DocumentExtractor",
    "PDFExtractor",
    "ImageExtractor",
    "VisionExtractor",
    "DocxExtractor",
    "get_extractor",
    "TextChunker",
    "OcrRefinementService",
    "OcrRefinementResult",
    "DocumentProcessor",
]

_LAZY_IMPORTS = {
    "DocumentUploadService": ("app.services.documents.upload", "DocumentUploadService"),
    "DocumentExtractor": ("app.services.documents.extraction", "DocumentExtractor"),
    "PDFExtractor": ("app.services.documents.extraction", "PDFExtractor"),
    "ImageExtractor": ("app.services.documents.extraction", "ImageExtractor"),
    "VisionExtractor": ("app.services.documents.extraction", "VisionExtractor"),
    "DocxExtractor": ("app.services.documents.extraction", "DocxExtractor"),
    "get_extractor": ("app.services.documents.extraction", "get_extractor"),
    "TextChunker": ("app.services.documents.chunking", "TextChunker"),
    "OcrRefinementService": (
        "app.services.documents.ocr_refinement",
        "OcrRefinementService",
    ),
    "OcrRefinementResult": (
        "app.services.documents.ocr_refinement",
        "OcrRefinementResult",
    ),
    "DocumentProcessor": ("app.services.documents.processor", "DocumentProcessor"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)
