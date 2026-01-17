"""RAG (Retrieval-Augmented Generation) service.

Combines the Context Engine with the LLM for medical Q&A.
"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context import ContextEngine
from app.services.llm.conversation import Conversation, ConversationManager
from app.services.llm.model import LLMService, LLMResponse


@dataclass
class RAGResponse:
    """Response from RAG service."""
    
    # LLM response
    answer: str
    llm_response: LLMResponse
    
    # Context used
    context_used: str
    num_sources: int
    sources_summary: list[dict]
    
    # Conversation
    conversation_id: UUID
    message_id: Optional[int] = None
    
    # Timing
    context_time_ms: float = 0.0
    generation_time_ms: float = 0.0
    total_time_ms: float = 0.0


class RAGService:
    """RAG service combining context retrieval with LLM generation.
    
    Workflow:
    1. Retrieve relevant context using Context Engine
    2. Build prompt with context
    3. Generate answer using MedGemma
    4. Store conversation history
    """
    
    # System prompt for medical Q&A
    DEFAULT_SYSTEM_PROMPT = """You are a medical assistant helping healthcare providers answer questions about patient medical history.

Guidelines:
- Use ONLY the provided patient context to answer questions
- Be precise and cite specific data points (dates, values, medications)
- If information is not in the context, clearly state that
- Do not make assumptions or provide information not in the context
- For medication questions, include dosage, frequency, and status (active/discontinued)
- For lab results, include values, units, and whether they are abnormal
- For dates, be specific and use the format provided in context
- If asked about trends, compare values over time when available
- Always prioritize patient safety and accuracy"""
    
    def __init__(
        self,
        db: AsyncSession,
        llm_service: Optional[LLMService] = None,
        context_engine: Optional[ContextEngine] = None,
        conversation_manager: Optional[ConversationManager] = None,
    ):
        """Initialize the RAG service.
        
        Args:
            db: Database session
            llm_service: LLM service instance
            context_engine: Context engine instance
            conversation_manager: Conversation manager instance
        """
        self.db = db
        self.llm_service = llm_service or LLMService.get_instance()
        self.context_engine = context_engine or ContextEngine(db)
        self.conversation_manager = conversation_manager or ConversationManager(db)
    
    async def ask(
        self,
        question: str,
        patient_id: int,
        conversation_id: Optional[UUID] = None,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 4000,
        use_conversation_history: bool = True,
    ) -> RAGResponse:
        """Ask a question about a patient using RAG.
        
        Args:
            question: User's question
            patient_id: Patient ID
            conversation_id: Optional existing conversation ID
            system_prompt: Override system prompt
            max_context_tokens: Maximum tokens for context
            use_conversation_history: Include conversation history in prompt
            
        Returns:
            RAGResponse with answer and metadata
        """
        import time
        total_start = time.time()
        
        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(patient_id)
            conversation_id = conversation.conversation_id
        
        # Add user message
        user_message = await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        
        # Get context
        context_start = time.time()
        context_result = await self.context_engine.get_context(
            query=question,
            patient_id=patient_id,
            max_tokens=max_context_tokens,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
        )
        context_time = (time.time() - context_start) * 1000
        
        # Build sources summary
        sources_summary = [
            {
                "source_type": r.result.source_type,
                "source_id": r.result.source_id,
                "relevance": r.final_score,
            }
            for r in context_result.ranked_results[:5]
        ]
        
        # Get conversation history (last few turns)
        conversation_history = None
        if use_conversation_history:
            conversation_history = conversation.get_last_n_turns(n=3)
        
        # Generate answer using the full prompt with context
        generation_start = time.time()
        llm_response = await self.llm_service.generate(
            prompt=context_result.prompt,
            max_new_tokens=512,
            conversation_history=conversation_history,
        )
        generation_time = (time.time() - generation_start) * 1000
        
        # Add assistant message
        assistant_message = await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=llm_response.text,
        )
        
        total_time = (time.time() - total_start) * 1000
        
        return RAGResponse(
            answer=llm_response.text,
            llm_response=llm_response,
            context_used=context_result.synthesized_context.full_context,
            num_sources=context_result.synthesized_context.total_chunks_used,
            sources_summary=sources_summary,
            conversation_id=conversation_id,
            message_id=assistant_message.message_id,
            context_time_ms=context_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
        )
    
    async def stream_ask(
        self,
        question: str,
        patient_id: int,
        conversation_id: Optional[UUID] = None,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 4000,
    ):
        """Stream answer generation.
        
        Yields:
            Text chunks as they are generated
        """
        # Get or create conversation
        if conversation_id:
            conversation = await self.conversation_manager.get_conversation(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = await self.conversation_manager.create_conversation(patient_id)
            conversation_id = conversation.conversation_id
        
        # Add user message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        
        # Get context
        context_result = await self.context_engine.get_context(
            query=question,
            patient_id=patient_id,
            max_tokens=max_context_tokens,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
        )
        
        # Stream generation
        full_answer = ""
        async for chunk in self.llm_service.stream_generate(
            prompt=context_result.prompt,
            system_prompt=None,  # Already in prompt
        ):
            full_answer += chunk
            yield chunk
        
        # Add assistant message
        await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_answer,
        )
    
    async def continue_conversation(
        self,
        conversation_id: UUID,
        question: str,
        system_prompt: Optional[str] = None,
        max_context_tokens: int = 4000,
    ) -> RAGResponse:
        """Continue an existing conversation.
        
        Args:
            conversation_id: Existing conversation ID
            question: New question
            system_prompt: Override system prompt
            max_context_tokens: Maximum context tokens
            
        Returns:
            RAGResponse with answer
        """
        # Get conversation
        conversation = await self.conversation_manager.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        return await self.ask(
            question=question,
            patient_id=conversation.patient_id,
            conversation_id=conversation_id,
            system_prompt=system_prompt,
            max_context_tokens=max_context_tokens,
            use_conversation_history=True,
        )
