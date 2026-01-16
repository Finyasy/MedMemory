from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    """Conversation model for storing chat sessions."""
    
    __tablename__ = "conversations"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(default=True)
    
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, patient_id={self.patient_id})>"


class ConversationMessage(Base, TimestampMixin):
    """Individual message in a conversation."""
    
    __tablename__ = "conversation_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="user, assistant, system"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    context_chunks: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON array of memory chunk IDs used for context"
    )
    
    prompt_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    feedback_rating: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="User rating 1-5"
    )
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    
    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role='{self.role}', content='{preview}')>"
