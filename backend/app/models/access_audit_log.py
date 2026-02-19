"""Audit log for patient data access (compliance)."""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class AccessAuditLog(Base, TimestampMixin):
    """Log of who accessed which patient data and when."""

    __tablename__ = "access_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="e.g. view_document, download, chat_query",
    )
    metadata_: Mapped[str | None] = mapped_column(
        "metadata",
        Text,
        nullable=True,
        comment="JSON or text: document_id, endpoint, etc.",
    )

    def __repr__(self) -> str:
        return f"<AccessAuditLog(id={self.id}, action={self.action}, patient_id={self.patient_id})>"
