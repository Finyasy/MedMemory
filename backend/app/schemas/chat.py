"""Pydantic schemas for Chat API."""

from datetime import datetime
from typing import Any
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
    message_id: int | None = None


# ============================================
# Conversation Schemas
# ============================================


class ConversationCreate(BaseModel):
    """Request to create a new conversation."""

    patient_id: int
    title: str | None = None


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
    conversation_id: UUID | None = None
    system_prompt: str | None = None
    max_context_tokens: int = Field(4000, ge=500, le=8000)
    use_conversation_history: bool = True


class SourceInfo(BaseModel):
    """Information about a source used in the answer."""

    source_type: str
    source_id: int | None = None
    relevance: float


class LabValue(BaseModel):
    """A single lab value with metadata.

    Handles both numeric and non-numeric lab values:
    - Numeric: "10.1", "72", "120/80"
    - Non-numeric: "Negative", "Trace", "<0.1", "1+", "O+", "POS", "NEG"

    Always store as string to preserve original format.
    """

    name: str = Field(..., description="Lab test name")
    value: str | None = Field(
        None, description="Lab value as string (e.g., '10.1', 'Negative', '<0.1', 'O+')"
    )
    value_num: float | None = Field(
        None, description="Numeric value if parseable (for sorting/comparison)"
    )
    unit: str | None = Field(
        None, description="Unit of measurement (e.g., 'g/dL', 'bpm', 'mmHg')"
    )
    date: str | None = Field(None, description="Date of test (YYYY-MM-DD format)")
    is_normal: bool | None = Field(None, description="Whether value is in normal range")
    source_snippet: str = Field(
        ..., description="REQUIRED: Exact text from document showing this value"
    )


class MedicationInfo(BaseModel):
    """Medication information."""

    name: str
    dosage: str | None = None
    frequency: str | None = None
    start_date: str | None = None
    source_snippet: str | None = None


class StructuredSummaryResponse(BaseModel):
    """Structured summary response."""

    overview: str = Field(..., description="One-sentence friendly overview")
    key_results: list[LabValue] = Field(default_factory=list)
    medications: list[MedicationInfo] = Field(default_factory=list)
    vital_signs: dict[str, str | None] = Field(
        default_factory=dict
    )  # e.g., {"pulse": "72 bpm", "bp": "120/80 mmHg"}
    follow_ups: list[str] = Field(
        default_factory=list, description="Recommended follow-up actions"
    )
    concerns: list[str] = Field(
        default_factory=list, description="Any concerns that need attention"
    )
    what_changed: list[str] = Field(
        default_factory=list,
        description="Record-grounded statements describing notable changes",
    )
    why_it_matters: list[str] = Field(
        default_factory=list,
        description="Record-grounded impact statements",
    )
    suggested_next_discussion_points: list[str] = Field(
        default_factory=list,
        description="Questions/topics to discuss with a clinician",
    )
    section_sources: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Section-level source chips (e.g. lab_result#41) for rendering "
            "under structured context-card sections."
        ),
    )
    source_document_id: int | None = None
    extraction_date: str | None = None


class ChatResponse(BaseModel):
    """Response from chat."""

    answer: str
    conversation_id: UUID
    message_id: int | None = None

    # Structured data (optional)
    structured_data: StructuredSummaryResponse | None = Field(
        None, description="Structured JSON response if requested"
    )

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


class VolumeChatResponse(BaseModel):
    """Response from volume interpretation."""

    answer: str
    total_slices: int
    sampled_indices: list[int] = []
    grid_rows: int
    grid_cols: int
    tile_size: int
    tokens_input: int = 0
    tokens_generated: int = 0
    tokens_total: int = 0
    generation_time_ms: float = 0.0


class WsiChatResponse(BaseModel):
    """Response from WSI patch interpretation."""

    answer: str
    total_patches: int
    sampled_indices: list[int] = []
    grid_rows: int
    grid_cols: int
    tile_size: int
    tokens_input: int = 0
    tokens_generated: int = 0
    tokens_total: int = 0
    generation_time_ms: float = 0.0


class CxrCompareResponse(BaseModel):
    """Response from longitudinal chest X-ray comparison."""

    answer: str
    tokens_input: int = 0
    tokens_generated: int = 0
    tokens_total: int = 0
    generation_time_ms: float = 0.0


class LocalizationBox(BaseModel):
    """Localized finding with pixel and normalized coordinates."""

    label: str
    confidence: float
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    x_min_norm: float
    y_min_norm: float
    x_max_norm: float
    y_max_norm: float


class LocalizationResponse(BaseModel):
    """Response from localization endpoint."""

    answer: str
    boxes: list[LocalizationBox] = []
    image_width: int
    image_height: int
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
    message_id: int | None = None
    num_sources: int | None = None
    sources: list[SourceInfo] | None = None
    structured_data: dict[str, Any] | None = None


# ============================================
# LLM Info
# ============================================


class LLMInfoResponse(BaseModel):
    """Information about the loaded LLM."""

    model_name: str
    device: str
    max_new_tokens: int
    temperature: float
    do_sample: bool = False
    top_p: float = 0.0
    top_k: int = 0
    repetition_penalty: float = 1.0
    vocab_size: int | None = None
    is_loaded: bool


class GuardrailCountersResponse(BaseModel):
    """Guardrail event counters for monitoring."""

    counters: dict[str, int] = Field(default_factory=dict)
    total: int = 0
