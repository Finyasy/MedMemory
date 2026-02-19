"""Clinician profile model for doctor dashboard."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ClinicianProfile(Base, TimestampMixin):
    """Clinician profile linked to a user (role=clinician)."""

    __tablename__ = "clinician_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    npi: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="NPI number"
    )
    license_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="clinician_profile")

    def __repr__(self) -> str:
        return f"<ClinicianProfile(id={self.id}, user_id={self.user_id})>"
