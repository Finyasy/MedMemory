"""Pydantic schemas for Chat API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================
# Message Schemas
# ============================================

class MessageSchema(BaseModel):
    """A message in a conversation."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    message_id: Optional[int] = None


# ============================================
# Conversation Schemas
# ============================================

class ConversationCreate(BaseModel):
    """Request to create a new conversation."""
    
    patient_id: int
    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """Response schema for a conversation."""
    
    conversation_id: UUID
    patient_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetail(ConversationResponse):
    """Detailed conversation with messages."""
    
    messages: list[MessageSchema] = []


# ============================================
# Chat Request/Response
# ============================================

class ChatRequest(BaseModel):
    """Request to chat with the AI."""
    
    question: str = Field(..., min_length=1, max_length=2000)
    patient_id: int
    conversation_id: Optional[UUID] = None
    system_prompt: Optional[str] = None
    max_context_tokens: int = Field(4000, ge=500, le=8000)
    use_conversation_history: bool = True


class SourceInfo(BaseModel):
    """Information about a source used in the answer."""
    
    source_type: str
    source_id: Optional[int] = None
    relevance: float


class ChatResponse(BaseModel):
    """Response from chat."""
    
    answer: str
    conversation_id: UUID
    message_id: Optional[int] = None
    
    # Context information
    num_sources: int = 0
    sources: list[SourceInfo] = []
    
    # Token usage
    tokens_input: int = 0
    tokens_generated: int = 0
    tokens_total: int = 0
    
    # Timing
    context_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0


# ============================================
# Vision Chat
# ============================================

class VisionChatResponse(BaseModel):
    """Response from vision chat."""

    answer: str
    tokens_input: int = 0
    tokens_generated: int = 0
    tokens_total: int = 0
    generation_time_ms: float = 0.0


# ============================================
# Stream Chat
# ============================================

class StreamChatChunk(BaseModel):
    """A chunk of streamed response."""
    
    chunk: str
    conversation_id: UUID
    is_complete: bool = False
    message_id: Optional[int] = None


# ============================================
# LLM Info
# ============================================

class LLMInfoResponse(BaseModel):
    """Information about the loaded LLM."""
    
    model_name: str
    device: str
    max_new_tokens: int
    temperature: float
    vocab_size: Optional[int] = None
    is_loaded: bool
