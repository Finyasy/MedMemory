"""RAG (Retrieval-Augmented Generation) service.

Combines the Context Engine with the LLM for medical Q&A.
"""

from dataclasses import dataclass
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
    DEFAULT_SYSTEM_PROMPT = """You are a medical assistant. Answer questions concisely using only the provided patient context.

Rules:
- Answer directly and briefly. No meta-commentary or explanations about your answer.
- If information is missing, simply state: "No information available about [topic]."
- Cite specific data (dates, values, medications) when available.
- Do not repeat the question or explain your reasoning process."""
    
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
        self.logger = logging.getLogger("medmemory")
    
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
        self.logger.info("ASK start patient=%s conv=%s", patient_id, conversation_id)
        
        # Add user message
        user_message = await self.conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=question,
        )
        
        # Get context
        context_start = time.time()
        effective_max_context_tokens = max_context_tokens
        if self.llm_service.device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)
        context_result = await self.context_engine.get_context(
            query=question,
            patient_id=patient_id,
            max_tokens=effective_max_context_tokens,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
        )
        self.logger.info("Context chars=%s", len(context_result.prompt))
        context_time = (time.time() - context_start) * 1000
        self.logger.info(
            "RAG context built device=%s context_tokens=%s time_ms=%.1f",
            self.llm_service.device,
            effective_max_context_tokens,
            context_time,
        )

        if not context_result.synthesized_context.total_chunks_used:
            answer = "No relevant information found in the patient's records."
            assistant_message = await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            )
            return RAGResponse(
                answer=answer,
                llm_response=LLMResponse(
                    text=answer,
                    tokens_generated=0,
                    tokens_input=0,
                    generation_time_ms=0.0,
                ),
                context_used=context_result.synthesized_context.full_context,
                num_sources=0,
                sources_summary=[],
                conversation_id=conversation_id,
                message_id=assistant_message.message_id,
                context_time_ms=context_time,
                generation_time_ms=0.0,
                total_time_ms=(time.time() - total_start) * 1000,
            )
        
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
        max_new_tokens = settings.llm_max_new_tokens
        if self.llm_service.device in ("mps", "cpu"):
            max_new_tokens = min(settings.llm_max_new_tokens, 256)
        llm_response = await self.llm_service.generate(
            prompt=context_result.prompt,
            max_new_tokens=max_new_tokens,
            conversation_history=conversation_history,
        )
        generation_time = (time.time() - generation_start) * 1000
        self.logger.info(
            "RAG generation done device=%s tokens_generated=%s time_ms=%.1f",
            self.llm_service.device,
            llm_response.tokens_generated,
            generation_time,
        )
        
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
        effective_max_context_tokens = max_context_tokens
        if self.llm_service.device in ("mps", "cpu"):
            effective_max_context_tokens = min(max_context_tokens, 2000)
        context_result = await self.context_engine.get_context(
            query=question,
            patient_id=patient_id,
            max_tokens=effective_max_context_tokens,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
        )
        self.logger.info(
            "RAG stream context built device=%s context_tokens=%s",
            self.llm_service.device,
            effective_max_context_tokens,
        )

        if not context_result.synthesized_context.total_chunks_used:
            answer = "No relevant information found in the patient's records."
            yield answer
            await self.conversation_manager.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
            )
            return
        
        # Stream generation
        full_answer = ""
        # MPS/CPU streaming can hang; fall back to single-shot generation.
        if self.llm_service.device in ("mps", "cpu"):
            max_new_tokens = min(settings.llm_max_new_tokens, 256)
            llm_response = await self.llm_service.generate(
                prompt=context_result.prompt,
                max_new_tokens=max_new_tokens,
                conversation_history=None,
            )
            full_answer = llm_response.text
            if full_answer:
                yield full_answer
        else:
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
