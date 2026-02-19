"""Business logic services for MedMemory.

This package intentionally avoids eager imports to prevent circular import
chains during application startup.
"""

from importlib import import_module

__all__ = [
    # Ingestion
    "IngestionService",
    "LabIngestionService",
    "MedicationIngestionService",
    "EncounterIngestionService",
    # Documents
    "DocumentUploadService",
    "DocumentProcessor",
    "TextChunker",
    "PDFExtractor",
    "ImageExtractor",
    # Embeddings
    "EmbeddingService",
    "MemoryIndexingService",
    "SimilaritySearchService",
    # Context Engine
    "QueryAnalyzer",
    "HybridRetriever",
    "ContextRanker",
    "ContextSynthesizer",
    "ContextEngine",
    # LLM
    "LLMService",
    "LLMResponse",
    "ConversationManager",
    "Conversation",
    "RAGService",
    "RAGResponse",
]

_LAZY_IMPORTS = {
    "IngestionService": ("app.services.ingestion", "IngestionService"),
    "LabIngestionService": ("app.services.ingestion", "LabIngestionService"),
    "MedicationIngestionService": (
        "app.services.ingestion",
        "MedicationIngestionService",
    ),
    "EncounterIngestionService": (
        "app.services.ingestion",
        "EncounterIngestionService",
    ),
    "DocumentUploadService": ("app.services.documents", "DocumentUploadService"),
    "DocumentProcessor": ("app.services.documents", "DocumentProcessor"),
    "TextChunker": ("app.services.documents", "TextChunker"),
    "PDFExtractor": ("app.services.documents", "PDFExtractor"),
    "ImageExtractor": ("app.services.documents", "ImageExtractor"),
    "EmbeddingService": ("app.services.embeddings", "EmbeddingService"),
    "MemoryIndexingService": ("app.services.embeddings", "MemoryIndexingService"),
    "SimilaritySearchService": ("app.services.embeddings", "SimilaritySearchService"),
    "QueryAnalyzer": ("app.services.context", "QueryAnalyzer"),
    "HybridRetriever": ("app.services.context", "HybridRetriever"),
    "ContextRanker": ("app.services.context", "ContextRanker"),
    "ContextSynthesizer": ("app.services.context", "ContextSynthesizer"),
    "ContextEngine": ("app.services.context", "ContextEngine"),
    "LLMService": ("app.services.llm", "LLMService"),
    "LLMResponse": ("app.services.llm", "LLMResponse"),
    "ConversationManager": ("app.services.llm", "ConversationManager"),
    "Conversation": ("app.services.llm", "Conversation"),
    "RAGService": ("app.services.llm", "RAGService"),
    "RAGResponse": ("app.services.llm", "RAGResponse"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)
