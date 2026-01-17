"""LLM service for MedGemma-4B-IT inference.

Handles model loading, tokenization, and text generation.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TextIteratorStreamer,
)

from app.config import settings


@dataclass
class LLMResponse:
    """Response from LLM inference."""
    
    text: str
    tokens_generated: int
    tokens_input: int
    generation_time_ms: float
    finish_reason: str = "stop"
    
    @property
    def total_tokens(self) -> int:
        return self.tokens_input + self.tokens_generated


class LLMService:
    """Service for running MedGemma-4B-IT inference.
    
    MedGemma-4B-IT is a medical instruction-tuned model based on Gemma.
    It's optimized for medical question answering and reasoning.
    """
    
    _instance: Optional["LLMService"] = None
    _model = None
    _tokenizer = None
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        load_in_4bit: bool = False,
    ):
        """Initialize the LLM service.
        
        Args:
            model_name: HuggingFace model name
            device: Device to run on ('cpu', 'cuda', 'mps')
            load_in_8bit: Use 8-bit quantization
            load_in_4bit: Use 4-bit quantization
        """
        self.model_name = model_name or settings.llm_model
        self.device = device or self._detect_device()
        self.load_in_8bit = load_in_8bit
        self.load_in_4bit = load_in_4bit
        
        # Generation parameters
        self.max_new_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.top_p = 0.9
        self.repetition_penalty = 1.1
        self.do_sample = True
    
    @classmethod
    def get_instance(cls) -> "LLMService":
        """Get singleton instance of LLM service."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def model(self):
        """Lazy-load the model."""
        if self._model is None:
            self._model = self._load_model()
        return self._model
    
    @property
    def tokenizer(self):
        """Lazy-load the tokenizer."""
        if self._tokenizer is None:
            self._tokenizer = self._load_tokenizer()
        return self._tokenizer
    
    def _detect_device(self) -> str:
        """Detect best available device."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _load_model(self):
        """Load the MedGemma model."""
        print(f"🔄 Loading LLM model: {self.model_name}")
        print(f"   Device: {self.device}")
        
        # Model loading kwargs
        model_kwargs = {
            "torch_dtype": torch.float16 if self.device != "cpu" else torch.float32,
            "device_map": "auto" if self.device != "cpu" else None,
            "trust_remote_code": True,
        }
        
        # Add quantization if requested
        if self.load_in_8bit:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif self.load_in_4bit:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
        
        # Load model
        try:
            model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                **model_kwargs,
            )
            
            if self.device == "cpu":
                model = model.to(self.device)
            
            model.eval()  # Set to evaluation mode
            print(f"✅ Model loaded successfully")
            
            return model
        
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise
    
    def _load_tokenizer(self):
        """Load the tokenizer."""
        print(f"🔄 Loading tokenizer for {self.model_name}")
        
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True,
        )
        
        # Set pad token if not set
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        print(f"✅ Tokenizer loaded")
        return tokenizer
    
    async def generate(
        self,
        prompt: str,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Generate text from a prompt.
        
        Args:
            prompt: Input prompt
            max_new_tokens: Override max tokens
            temperature: Override temperature
            system_prompt: Optional system prompt
            conversation_history: Previous conversation turns
            
        Returns:
            LLMResponse with generated text
        """
        import time
        start_time = time.time()
        
        # Build full prompt
        full_prompt = self._build_prompt(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )
        
        # Tokenize
        inputs = self.tokenizer(
            full_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048,  # Max input length
        ).to(self.device)
        
        input_tokens = inputs.input_ids.shape[1]
        
        # Generation parameters
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_new_tokens,
            "temperature": temperature or self.temperature,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": self.do_sample,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        
        # Generate in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        outputs = await loop.run_in_executor(
            None,
            lambda: self.model.generate(**inputs, **gen_kwargs),
        )
        
        # Decode
        generated_text = self.tokenizer.decode(
            outputs[0][input_tokens:],
            skip_special_tokens=True,
        )
        
        output_tokens = outputs[0].shape[1] - input_tokens
        generation_time = (time.time() - start_time) * 1000
        
        return LLMResponse(
            text=generated_text.strip(),
            tokens_generated=output_tokens,
            tokens_input=input_tokens,
            generation_time_ms=generation_time,
        )
    
    def _build_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ) -> str:
        """Build the full prompt with system message and history."""
        parts = []
        
        # System prompt
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")
        
        # Conversation history
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "user":
                    parts.append(f"User: {content}\n")
                elif role == "assistant":
                    parts.append(f"Assistant: {content}\n")
        
        # Current prompt
        parts.append(f"User: {prompt}\n")
        parts.append("Assistant:")
        
        return "".join(parts)
    
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[list[dict]] = None,
    ):
        """Stream generated text token by token.
        
        Yields:
            Generated text chunks
        """
        # Build prompt
        full_prompt = self._build_prompt(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )
        
        # Tokenize
        inputs = self.tokenizer(
            full_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
        ).to(self.device)
        
        # Create streamer
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        
        # Generation kwargs
        gen_kwargs = {
            **inputs,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": self.do_sample,
            "streamer": streamer,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        
        # Generate in background thread
        loop = asyncio.get_event_loop()
        generation_task = loop.run_in_executor(
            None,
            lambda: self.model.generate(**gen_kwargs),
        )
        
        # Stream tokens
        async for token in self._async_streamer(streamer):
            yield token
        
        # Wait for generation to complete
        await generation_task
    
    async def _async_streamer(self, streamer: TextIteratorStreamer):
        """Async wrapper for text streamer."""
        while True:
            try:
                token = await asyncio.to_thread(streamer.__next__)
                yield token
            except StopIteration:
                break
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "vocab_size": len(self.tokenizer) if self.tokenizer else None,
            "is_loaded": self._model is not None,
        }
