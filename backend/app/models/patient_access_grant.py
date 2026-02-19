"""Patient access grant: allows a clinician to access a patient's data."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class GrantStatus(StrEnum):
    pending = "pending"
    active = "active"
    revoked = "revoked"
    expired = "expired"


class PatientAccessGrant(Base, TimestampMixin):
    """Grants a clinician access to a patient's data (documents, records, labs, chat)."""

    __tablename__ = "patient_access_grants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    clinician_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    granted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Patient owner who granted access",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=GrantStatus.pending.value,
        server_default="pending",
    )
    scopes: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="documents,records,labs,medications,chat",
        comment="Comma-separated: documents, records, labs, medications, chat",
    )

    granted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    patient: Mapped["Patient"] = relationship(back_populates="access_grants")
    clinician: Mapped["User"] = relationship(
        foreign_keys=[clinician_user_id],
        back_populates="access_grants_as_clinician",
    )

    def has_scope(self, scope: str) -> bool:
        """Check if this grant includes the given scope."""
        return scope in (s.strip() for s in self.scopes.split(","))

    def __repr__(self) -> str:
        return f"<PatientAccessGrant(patient_id={self.patient_id}, clinician_user_id={self.clinician_user_id}, status={self.status})>"
