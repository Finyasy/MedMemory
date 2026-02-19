"""Persistent JWT blacklist entries."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TokenBlacklist(Base, TimestampMixin):
    """Stores revoked JWT identifiers (jti) until expiration."""

    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    token_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="access"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TokenBlacklist(jti={self.jti}, token_type={self.token_type})>"
