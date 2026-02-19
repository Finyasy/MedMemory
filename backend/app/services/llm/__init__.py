"""LLM services for MedMemory.

Provides inference with MedGemma-4B-IT for medical Q&A.
"""

from importlib import import_module

__all__ = [
    "LLMService",
    "LLMResponse",
    "ConversationManager",
    "Conversation",
    "RAGService",
    "RAGResponse",
]

_LAZY_IMPORTS = {
    "LLMService": ("app.services.llm.model", "LLMService"),
    "LLMResponse": ("app.services.llm.model", "LLMResponse"),
    "ConversationManager": ("app.services.llm.conversation", "ConversationManager"),
    "Conversation": ("app.services.llm.conversation", "Conversation"),
    "RAGService": ("app.services.llm.rag", "RAGService"),
    "RAGResponse": ("app.services.llm.rag", "RAGResponse"),
}


def __getattr__(name: str):
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    return getattr(import_module(module_name), attr_name)
