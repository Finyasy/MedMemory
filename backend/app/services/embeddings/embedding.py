"""Embedding service using sentence-transformers.

Generates vector embeddings for text that can be used for
semantic similarity search.
"""

import asyncio
import logging
from functools import lru_cache
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger("medmemory")


class MissingMLDependencyError(RuntimeError):
    """Raised when an embedding dependency is missing at runtime."""


class EmbeddingService:
    """Service for generating text embeddings.

    Uses sentence-transformers models to create dense vector
    representations of text for semantic search.

    Supported models:
    - all-MiniLM-L6-v2 (384 dims, fast, good quality)
    - all-mpnet-base-v2 (768 dims, slower, better quality)
    - multi-qa-MiniLM-L6-cos-v1 (384 dims, optimized for Q&A)
    """

    _instance: Optional["EmbeddingService"] = None
    _model = None

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ):
        """Initialize the embedding service.

        Args:
            model_name: Name of the sentence-transformers model
            device: Device to run on ('cpu', 'cuda', 'mps')
        """
        self.model_name = model_name or settings.embedding_model
        self.device = device or self._detect_device()
        self._model = None

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        """Get singleton instance of embedding service.

        Using singleton pattern to avoid loading the model multiple times.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension for current model."""
        return self.model.get_sentence_embedding_dimension()

    def _detect_device(self) -> str:
        """Detect best available device."""
        try:
            import torch
        except ModuleNotFoundError as exc:
            missing_package = exc.name or "torch"
            raise MissingMLDependencyError(
                f"Missing required ML dependency '{missing_package}' for embeddings. "
                "Install backend dependencies with: cd backend && uv sync "
                f"(or add directly with: cd backend && uv add {missing_package})."
            ) from exc

        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load_model(self):
        """Load the sentence-transformers model."""
        import os

        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            missing_package = exc.name or "sentence-transformers"
            install_name = (
                "sentence-transformers"
                if missing_package == "sentence_transformers"
                else missing_package
            )
            raise MissingMLDependencyError(
                f"Missing required ML dependency '{missing_package}' while "
                "loading embeddings. "
                "Install backend dependencies with: cd backend && uv sync "
                f"(or add directly with: cd backend && uv add {install_name})."
            ) from exc
        except ImportError as exc:
            raise MissingMLDependencyError(
                "Failed to import sentence-transformers for embeddings. "
                "Reinstall backend dependencies with: cd backend && uv sync."
            ) from exc

        # Set offline mode if configured
        if settings.hf_hub_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            logger.info("Running in HF_HUB_OFFLINE mode")
        if settings.transformers_offline:
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            logger.info("Running in TRANSFORMERS_OFFLINE mode")

        logger.info("Loading embedding model: %s", self.model_name)

        # Use cache directory if specified
        cache_kwargs = {}
        if settings.hf_cache_dir:
            cache_kwargs["cache_folder"] = str(settings.hf_cache_dir)

        try:
            model = SentenceTransformer(
                self.model_name,
                device=self.device,
                **cache_kwargs,
            )
        except ModuleNotFoundError as exc:
            missing_package = exc.name or "unknown"
            raise MissingMLDependencyError(
                f"Missing required ML dependency '{missing_package}' while "
                "constructing embeddings model. "
                "Install backend dependencies with: cd backend && uv sync "
                f"(or add directly with: cd backend && uv add {missing_package})."
            ) from exc
        logger.info(
            "Embedding model loaded on %s (dim=%d)",
            self.device,
            model.get_sentence_embedding_dimension(),
        )

        return model

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )

        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [t for t in texts if t and t.strip()]

        if not valid_texts:
            return []

        embeddings = self.model.encode(
            valid_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(valid_texts) > 10,
            batch_size=32,
        )

        return embeddings.tolist()

    async def embed_text_async(self, text: str) -> list[float]:
        """Async wrapper for embed_text.

        Runs embedding in thread pool to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_text, text)

    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper for embed_texts.

        Runs embedding in thread pool to avoid blocking.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_texts, texts)

    def compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1 for normalized vectors)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity (dot product for normalized vectors)
        similarity = np.dot(vec1, vec2)

        return float(similarity)

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query.

        Some models have special handling for queries vs documents.
        This method can be extended for query-specific processing.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        # Clean and normalize query
        query = query.strip()

        # For now, use same embedding as documents
        # Future: Could use query-specific models or prefixes
        return self.embed_text(query)

    async def embed_query_async(self, query: str) -> list[float]:
        """Async wrapper for embed_query."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embed_query, query)


# Convenience function for getting embeddings
@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    return EmbeddingService.get_instance()
