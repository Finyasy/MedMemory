"""Embedding and vector search services for MedMemory."""

from importlib import import_module

__all__ = [
    "EmbeddingService",
    "MissingMLDependencyError",
    "MemoryIndexingService",
    "SimilaritySearchService",
]

_LAZY_IMPORTS = {
    "EmbeddingService": ("app.services.embeddings.embedding", "EmbeddingService"),
    "MissingMLDependencyError": (
        "app.services.embeddings.embedding",
        "MissingMLDependencyError",
    ),
    "MemoryIndexingService": (
        "app.services.embeddings.indexing",
        "MemoryIndexingService",
    ),
    "SimilaritySearchService": (
        "app.services.embeddings.search",
        "SimilaritySearchService",
    ),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)
