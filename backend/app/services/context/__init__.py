"""Context engine services for MedMemory.

The context engine provides intelligent retrieval of medical information
by combining multiple retrieval strategies and ranking results.
"""

from importlib import import_module

__all__ = [
    "QueryAnalyzer",
    "QueryAnalysis",
    "HybridRetriever",
    "RetrievalResult",
    "ContextRanker",
    "ContextSynthesizer",
    "ContextEngine",
]

_LAZY_IMPORTS = {
    "QueryAnalyzer": ("app.services.context.analyzer", "QueryAnalyzer"),
    "QueryAnalysis": ("app.services.context.analyzer", "QueryAnalysis"),
    "HybridRetriever": ("app.services.context.retriever", "HybridRetriever"),
    "RetrievalResult": ("app.services.context.retriever", "RetrievalResult"),
    "ContextRanker": ("app.services.context.ranker", "ContextRanker"),
    "ContextSynthesizer": ("app.services.context.synthesizer", "ContextSynthesizer"),
    "ContextEngine": ("app.services.context.engine", "ContextEngine"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)
