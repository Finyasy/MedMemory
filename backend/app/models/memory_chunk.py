from datetime import datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient

# Embedding dimension for sentence-transformers models
# all-MiniLM-L6-v2: 384, all-mpnet-base-v2: 768
EMBEDDING_DIMENSION = settings.embedding_dimension


class MemoryChunk(Base, TimestampMixin):
    """Memory chunk model for storing text with vector embeddings.

    This is the core of the semantic memory system, enabling
    similarity search across the patient's medical history.
    """

    __tablename__ = "memory_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="Hash of content for deduplication"
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="Model used to generate embedding"
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="e.g., lab_result, medication, encounter, document",
    )
    source_id: Mapped[int | None] = mapped_column(
        nullable=True, comment="ID of the source record"
    )
    source_table: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Table name of the source record"
    )

    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(
        nullable=True, comment="Position of chunk within the source"
    )

    context_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date this information is relevant to",
    )

    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Additional metadata as JSON"
    )
    chunk_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="e.g., summary, detail, note"
    )
    importance_score: Mapped[float | None] = mapped_column(
        nullable=True, comment="Relevance/importance ranking 0-1"
    )

    is_indexed: Mapped[bool] = mapped_column(default=False, index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(back_populates="memory_chunks")

    __table_args__ = (
        Index(
            "idx_memory_chunks_embedding",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 128},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_memory_chunks_patient_created", "patient_id", "created_at"),
    )

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<MemoryChunk(id={self.id}, source='{self.source_type}', content='{preview}')>"
