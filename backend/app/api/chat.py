"""Chat API endpoints for medical Q&A.

Provides conversational interface using RAG with MedGemma-4B-IT.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_authenticated_user, get_patient_for_user
from app.database import get_db
from app.models import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationResponse,
    LLMInfoResponse,
    MessageSchema,
    SourceInfo,
    StreamChatChunk,
    VisionChatResponse,
)
from app.services.llm import LLMService, RAGService
from app.services.llm.conversation import ConversationManager

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============================================
# Chat Endpoints
# ============================================

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Ask a question about a patient using RAG.
    
    This endpoint:
    1. Retrieves relevant context from patient records
    2. Generates an answer using MedGemma-4B-IT
    3. Stores the conversation for history
    
    Example questions:
    - "What medications is the patient currently taking?"
    - "Show me any abnormal lab results from the past year"
    - "What is the patient's diagnosis history?"
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    # Run RAG
    rag_service = RAGService(db)
    rag_response = await rag_service.ask(
        question=request.question,
        patient_id=request.patient_id,
        conversation_id=request.conversation_id,
        system_prompt=request.system_prompt,
        max_context_tokens=request.max_context_tokens,
        use_conversation_history=request.use_conversation_history,
    )
    
    return ChatResponse(
        answer=rag_response.answer,
        conversation_id=rag_response.conversation_id,
        message_id=rag_response.message_id,
        num_sources=rag_response.num_sources,
        sources=[
            SourceInfo(
                source_type=s["source_type"],
                source_id=s["source_id"],
                relevance=s["relevance"],
            )
            for s in rag_response.sources_summary
        ],
        tokens_input=rag_response.llm_response.tokens_input,
        tokens_generated=rag_response.llm_response.tokens_generated,
        tokens_total=rag_response.llm_response.total_tokens,
        context_time_ms=rag_response.context_time_ms,
        generation_time_ms=rag_response.generation_time_ms,
        total_time_ms=rag_response.total_time_ms,
    )


@router.post("/stream")
async def stream_ask(
    question: str = Query(..., min_length=1, max_length=2000),
    patient_id: int = Query(...),
    conversation_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Stream answer generation token by token.
    
    Useful for real-time chat interfaces where you want to show
    the answer as it's being generated.
    """
    # Verify patient exists
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )
    
    # Get or create conversation
    manager = ConversationManager(db)
    conversation_uuid = conversation_id
    if conversation_uuid is None:
        conversation = await manager.create_conversation(patient_id=patient_id)
        conversation_uuid = conversation.conversation_id
    
    rag_service = RAGService(db)
    
    async def generate():
        async for chunk in rag_service.stream_ask(
            question=question,
            patient_id=patient_id,
            conversation_id=conversation_uuid,
        ):
            yield f"data: {StreamChatChunk(chunk=chunk, conversation_id=conversation_uuid, is_complete=False).model_dump_json()}\n\n"
        
        # Send completion with conversation ID
        yield f"data: {StreamChatChunk(chunk='', conversation_id=conversation_uuid, is_complete=True).model_dump_json()}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/vision", response_model=VisionChatResponse)
async def ask_with_image(
    prompt: str = Form(..., min_length=1, max_length=2000),
    patient_id: int = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Analyze a medical image using the vision-language model."""
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    llm_service = LLMService.get_instance()
    system_prompt = (
        "You are a medical imaging assistant. Respond in simple English a customer can understand. "
        "Write 3-5 short sentences in a calm, reassuring tone. "
        "Do not use bullet points or numbering. "
        "Do not repeat findings. Do not list speculative nodules. "
        "If unsure, say \"may be\" and keep it brief. "
        "No greetings, apologies, or extra commentary. "
        "If the image is not diagnostic, respond exactly: \"No diagnostic information available.\""
    )
    llm_response = await llm_service.generate_with_image(
        prompt=prompt,
        image_bytes=image_bytes,
        system_prompt=system_prompt,
        max_new_tokens=220,
    )

    return VisionChatResponse(
        answer=llm_response.text,
        tokens_input=llm_response.tokens_input,
        tokens_generated=llm_response.tokens_generated,
        tokens_total=llm_response.total_tokens,
        generation_time_ms=llm_response.generation_time_ms,
    )


# ============================================
# Conversation Management
# ============================================

@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    request: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Create a new conversation."""
    # Verify patient exists
    await get_patient_for_user(
        patient_id=request.patient_id,
        db=db,
        current_user=current_user,
    )
    
    manager = ConversationManager(db)
    conversation = await manager.create_conversation(
        patient_id=request.patient_id,
        title=request.title,
    )
    
    return ConversationResponse(
        conversation_id=conversation.conversation_id,
        patient_id=conversation.patient_id,
        title=conversation.title or "New Conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Get a conversation with all messages."""
    manager = ConversationManager(db)
    conversation = await manager.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await get_patient_for_user(
        patient_id=conversation.patient_id,
        db=db,
        current_user=current_user,
    )
    
    return ConversationDetail(
        conversation_id=conversation.conversation_id,
        patient_id=conversation.patient_id,
        title=conversation.title or "Conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        messages=[
            MessageSchema(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
                message_id=msg.message_id,
            )
            for msg in conversation.messages
        ],
    )


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    patient_id: int = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """List conversations for a patient."""
    await get_patient_for_user(
        patient_id=patient_id,
        db=db,
        current_user=current_user,
    )
    manager = ConversationManager(db)
    conversations = await manager.list_conversations(patient_id, limit)
    
    return [
        ConversationResponse(
            conversation_id=conv.conversation_id,
            patient_id=conv.patient_id,
            title=conv.title or "Conversation",
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=len(conv.messages),
        )
        for conv in conversations
    ]


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    manager = ConversationManager(db)
    deleted = await manager.delete_conversation(conversation_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.patch("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: UUID,
    title: str = Query(..., min_length=1, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    """Update conversation title."""
    manager = ConversationManager(db)
    updated = await manager.update_title(conversation_id, title)
    
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {"title": title}


# ============================================
# LLM Info
# ============================================
