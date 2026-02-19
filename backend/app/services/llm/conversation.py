"""Conversation management for chat history.

Manages conversation state and history for multi-turn dialogues.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation as ConversationModel
from app.models import ConversationMessage as MessageModel


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    message_id: int | None = None


@dataclass
class Conversation:
    """A conversation with a patient."""

    conversation_id: UUID
    patient_id: int
    title: str | None = None
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, role: str, content: str) -> Message:
        """Add a message to the conversation."""
        message = Message(role=role, content=content)
        self.messages.append(message)
        self.updated_at = datetime.now(UTC)
        return message

    def to_history(self) -> list[dict]:
        """Convert to format expected by LLM."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def get_last_n_turns(self, n: int = 5) -> list[dict]:
        """Get last N conversation turns for context."""
        return self.to_history()[-n * 2 :] if n > 0 else self.to_history()


class ConversationManager:
    """Manages conversation state and persistence.

    Handles:
    - Creating new conversations
    - Adding messages
    - Retrieving conversation history
    - Updating conversation metadata
    """

    def __init__(self, db: AsyncSession):
        """Initialize the conversation manager.

        Args:
            db: Database session
        """
        self.db = db

    async def create_conversation(
        self,
        patient_id: int,
        title: str | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            patient_id: Patient ID
            title: Optional conversation title

        Returns:
            Created Conversation
        """
        conversation_id = uuid4()

        db_conversation = ConversationModel(
            id=conversation_id,
            patient_id=patient_id,
            title=title
            or f"Conversation {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}",
        )

        self.db.add(db_conversation)
        await self.db.flush()
        await self.db.refresh(db_conversation)

        return Conversation(
            conversation_id=conversation_id,
            patient_id=patient_id,
            title=db_conversation.title,
            created_at=db_conversation.created_at,
            updated_at=db_conversation.updated_at,
        )

    async def get_conversation(
        self,
        conversation_id: UUID,
    ) -> Conversation | None:
        """Get a conversation by ID.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Conversation or None if not found
        """
        # Get conversation
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        db_conversation = result.scalar_one_or_none()

        if not db_conversation:
            return None

        # Get messages
        result = await self.db.execute(
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )
        db_messages = result.scalars().all()

        # Build conversation
        conversation = Conversation(
            conversation_id=conversation_id,
            patient_id=db_conversation.patient_id,
            title=db_conversation.title,
            created_at=db_conversation.created_at,
            updated_at=db_conversation.updated_at,
        )

        # Add messages
        for db_msg in db_messages:
            conversation.messages.append(
                Message(
                    role=db_msg.role,
                    content=db_msg.content,
                    timestamp=db_msg.created_at,
                    message_id=db_msg.id,
                )
            )

        return conversation

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation UUID
            role: Message role ('user' or 'assistant')
            content: Message content

        Returns:
            Created Message
        """
        # Verify conversation exists
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Create message
        db_message = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        self.db.add(db_message)
        await self.db.flush()
        await self.db.refresh(db_message)

        # Add to conversation object
        message = Message(
            role=role,
            content=content,
            timestamp=db_message.created_at,
            message_id=db_message.id,
        )
        conversation.messages.append(message)
        conversation.updated_at = datetime.now(UTC)

        # Update conversation timestamp
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        db_conv = result.scalar_one()
        db_conv.updated_at = datetime.now(UTC)
        await self.db.flush()

        return message

    async def list_conversations(
        self,
        patient_id: int,
        limit: int = 20,
    ) -> list[Conversation]:
        """List conversations for a patient.

        Args:
            patient_id: Patient ID
            limit: Maximum number of conversations

        Returns:
            List of conversations
        """
        result = await self.db.execute(
            select(ConversationModel)
            .where(ConversationModel.patient_id == patient_id)
            .order_by(ConversationModel.updated_at.desc())
            .limit(limit)
        )
        db_conversations = result.scalars().all()

        conversations = []
        for db_conv in db_conversations:
            conversations.append(
                Conversation(
                    conversation_id=db_conv.id,
                    patient_id=db_conv.patient_id,
                    title=db_conv.title,
                    created_at=db_conv.created_at,
                    updated_at=db_conv.updated_at,
                )
            )

        return conversations

    async def delete_conversation(
        self,
        conversation_id: UUID,
    ) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if deleted, False if not found
        """
        from sqlalchemy import delete

        # Delete messages first
        await self.db.execute(
            delete(MessageModel).where(MessageModel.conversation_id == conversation_id)
        )

        # Delete conversation
        result = await self.db.execute(
            delete(ConversationModel).where(ConversationModel.id == conversation_id)
        )

        return result.rowcount > 0

    async def update_title(
        self,
        conversation_id: UUID,
        title: str,
    ) -> bool:
        """Update conversation title.

        Args:
            conversation_id: Conversation UUID
            title: New title

        Returns:
            True if updated, False if not found
        """
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        db_conv = result.scalar_one_or_none()

        if not db_conv:
            return False

        db_conv.title = title
        await self.db.flush()
        return True
