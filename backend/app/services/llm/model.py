"""LLM service for MedGemma-1.5-4B-IT inference.

Handles model loading, tokenization, and text generation.
Optimized for MPS (Apple Silicon) and CUDA.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch
from transformers import (
    AutoModelForImageTextToText,
    AutoProcessor,
    BitsAndBytesConfig,
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
    """Service for running MedGemma-1.5-4B-IT inference.
    
    MedGemma-1.5-4B-IT is a medical instruction-tuned vision-language model based on Gemma.
    It's optimized for medical question answering and reasoning.
    Supports text-only and multimodal inputs.
    """
    
    _instance: Optional["LLMService"] = None
    _model = None
    _processor = None
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[Path] = None,
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        load_in_4bit: Optional[bool] = None,
    ):
        """Initialize the LLM service.
        
        Args:
            model_name: HuggingFace model name (used if model_path not set)
            model_path: Local path to model directory (overrides model_name)
            device: Device to run on ('cpu', 'cuda', 'mps')
            load_in_8bit: Use 8-bit quantization
            load_in_4bit: Use 4-bit quantization (defaults to settings.llm_quantize_4bit)
        """
        # Determine model path/name
        # Resolve relative paths relative to backend directory
        backend_dir = Path(__file__).resolve().parents[3]
        
        if model_path:
            self.model_path = Path(model_path)
            if not self.model_path.is_absolute():
                self.model_path = (backend_dir / self.model_path).resolve()
            elif not self.model_path.exists() and "app" in self.model_path.parts and "models" in self.model_path.parts:
                candidate = (backend_dir / "models" / self.model_path.name).resolve()
                if candidate.exists():
                    self.model_path = candidate
            self.model_name = str(self.model_path)
            self.use_local_model = True
        elif settings.llm_model_path:
            self.model_path = Path(settings.llm_model_path)
            if not self.model_path.is_absolute():
                self.model_path = (backend_dir / self.model_path).resolve()
            elif not self.model_path.exists() and "app" in self.model_path.parts and "models" in self.model_path.parts:
                candidate = (backend_dir / "models" / self.model_path.name).resolve()
                if candidate.exists():
                    self.model_path = candidate
            self.model_name = str(self.model_path)
            self.use_local_model = True
        else:
            self.model_path = None
            self.model_name = model_name or settings.llm_model
            self.use_local_model = False
        
        self.device = device or self._detect_device()
        self.load_in_8bit = load_in_8bit
        
        # Default to settings value if not explicitly set
        if load_in_4bit is None:
            self.load_in_4bit = settings.llm_quantize_4bit
        else:
            self.load_in_4bit = load_in_4bit
        
        # Generation parameters
        self.max_new_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.top_p = 0.9
        self.repetition_penalty = 1.1
        # MPS stability: disable sampling by default.
        self.do_sample = False
        # Serialize generations on MPS to avoid hangs under concurrent load.
        self._gen_lock = asyncio.Lock()
    
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
    def processor(self):
        """Lazy-load the processor."""
        if self._processor is None:
            self._processor = self._load_processor()
        return self._processor
    
    @property
    def tokenizer(self):
        """Compatibility property - returns processor."""
        return self.processor
    
    def _detect_device(self) -> str:
        """Detect best available device (CUDA, MPS, or CPU)."""
        if torch.cuda.is_available():
            return "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _pick_dtype(self) -> torch.dtype:
        """Pick optimal dtype based on device."""
        if self.device == "mps":
            # Apple Silicon supports bfloat16 well
            try:
                return torch.bfloat16
            except Exception:
                return torch.float16
        elif self.device == "cuda":
            return torch.float16
        return torch.float32
    
    def _load_model(self):
        """Load the MedGemma model from local path or Hugging Face.
        
        Optimized for MPS (Apple Silicon) and CUDA.
        """
        source = "local path" if self.use_local_model else "Hugging Face"
        print(f"🔄 Loading LLM model from {source}: {self.model_name}")
        print(f"   Device: {self.device}")
        
        dtype = self._pick_dtype()
        print(f"   DType: {dtype}")
        
        # Model loading kwargs
        model_kwargs = {
            "dtype": dtype,  # Use dtype instead of torch_dtype (deprecated)
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,  # Reduces peak RAM during load
        }
        
        # Use local_files_only if loading from local path
        if self.use_local_model:
            model_kwargs["local_files_only"] = True
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Model path not found: {self.model_path}. "
                    f"Please download the model first using: python scripts/download_model.py"
                )
        
        # Configure device mapping
        # - CUDA: device_map="auto" works well
        # - MPS: move to MPS explicitly after load (device_map isn't consistently supported)
        if self.device == "cuda":
            model_kwargs["device_map"] = "auto"
        # For MPS and CPU, we'll move manually after loading
        
        # Add quantization if requested (CUDA only)
        quant_cfg = None
        if self.load_in_4bit and self.device == "cuda":
            print("   Using INT4 (4-bit) quantization with best practices")
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            model_kwargs["quantization_config"] = quant_cfg
        elif self.load_in_8bit and self.device == "cuda":
            print("   Using INT8 (8-bit) quantization")
            quant_cfg = BitsAndBytesConfig(load_in_8bit=True)
            model_kwargs["quantization_config"] = quant_cfg
        elif (self.load_in_4bit or self.load_in_8bit) and self.device != "cuda":
            print("   ⚠️  Warning: 4-bit quantization requires CUDA. Skipping quantization.")
        
        # Load model
        try:
            model = AutoModelForImageTextToText.from_pretrained(
                self.model_name,
                **model_kwargs,
            )
            
            # Move to device if not using device_map
            if self.device == "mps":
                model = model.to("mps")
            elif self.device == "cpu" and "device_map" not in model_kwargs:
                model = model.to("cpu")
            
            model.eval()  # Set to evaluation mode
            
            # Display model info
            if quant_cfg:
                print(f"✅ Model loaded successfully with quantization")
            else:
                print(f"✅ Model loaded successfully")
            
            # Show memory usage
            if self.device == "cuda" and torch.cuda.is_available():
                memory_gb = torch.cuda.memory_allocated() / 1e9
                print(f"   GPU memory used: {memory_gb:.2f} GB")
            elif self.device == "mps":
                # MPS doesn't have direct memory reporting, but we can check model size
                param_count = sum(p.numel() for p in model.parameters())
                print(f"   Model parameters: {param_count / 1e9:.2f}B")
            
            return model
        
        except ImportError as e:
            if "bitsandbytes" in str(e):
                raise ImportError(
                    "bitsandbytes is required for 4-bit quantization. "
                    "Install it with: pip install bitsandbytes"
                ) from e
            raise
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            if self.use_local_model:
                print(f"   Hint: Make sure the model is downloaded to: {self.model_path}")
                print(f"   Run: python scripts/download_model.py")
            raise
    
    def _load_processor(self):
        """Load the processor from local path or Hugging Face.
        
        MedGemma uses AutoProcessor which handles both text and vision inputs.
        """
        print(f"🔄 Loading processor for {self.model_name}")
        
        processor_kwargs = {
            "trust_remote_code": True,
        }
        
        # Use local_files_only if loading from local path
        if self.use_local_model:
            processor_kwargs["local_files_only"] = True
        
        processor = AutoProcessor.from_pretrained(
            self.model_name,
            use_fast=True,  # Use fast processor to avoid deprecation warning
            **processor_kwargs,
        )
        
        print(f"✅ Processor loaded")
        return processor
    
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
        
        # Build full prompt (skip wrapping if prompt is already composed)
        if system_prompt is None and not conversation_history:
            full_prompt = prompt
        else:
            full_prompt = self._build_prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )
        
        # Process text input (processor handles tokenization for vision-language models)
        inputs = self.processor(
            text=full_prompt,
            return_tensors="pt",
        )
        
        # Move inputs to the model's actual device
        model_device = next(self.model.parameters()).device
        inputs = {k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()}
        
        if "input_ids" in inputs:
            print("LLM generate: input_ids shape", inputs["input_ids"].shape)
        print("LLM device:", next(self.model.parameters()).device)
        input_tokens = inputs["input_ids"].shape[1] if "input_ids" in inputs else 0
        
        # Generation parameters
        tokenizer = self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": self.do_sample,
        }
        # Only include sampling parameters when do_sample=True
        if self.do_sample:
            gen_kwargs.update({
                "temperature": temperature or self.temperature,
                "top_p": self.top_p,
            })
        if tokenizer:
            gen_kwargs.update({
                "eos_token_id": tokenizer.eos_token_id,
                "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
            })
        
        # Generate in thread pool to avoid blocking, using inference_mode for efficiency
        loop = asyncio.get_event_loop()
        
        def _generate():
            with torch.inference_mode():
                return self.model.generate(**inputs, **gen_kwargs)
        
        async with self._gen_lock:
            outputs = await loop.run_in_executor(None, _generate)
        
        # Normalize outputs to generated token ids
        sequences = outputs
        if hasattr(outputs, "sequences"):
            sequences = outputs.sequences
        elif isinstance(outputs, (tuple, list)):
            sequences = outputs[0]
        
        if not hasattr(sequences, "shape") or len(sequences.shape) < 2:
            raise RuntimeError(
                f"Unexpected generate() output type/shape: {type(outputs)} / {getattr(sequences, 'shape', None)}"
            )
        
        seq = sequences[0]
        input_len = inputs["input_ids"].shape[-1] if "input_ids" in inputs else 0
        generated_ids = seq[input_len:] if input_len > 0 else seq
        
        # Decode using processor
        tokenizer = self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        if tokenizer:
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
        else:
            generated_text = self.processor.batch_decode([generated_ids], skip_special_tokens=True)[0]
        
        output_tokens = max(int(seq.shape[0] - input_len), 0)
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
        
        # Process text input
        inputs = self.processor(
            text=full_prompt,
            return_tensors="pt",
        )
        
        # Move inputs to the model's actual device
        model_device = next(self.model.parameters()).device
        inputs = {k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()}
        
        # Create streamer (using processor's tokenizer)
        tokenizer = self.processor.tokenizer if hasattr(self.processor, "tokenizer") else self.processor
        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        
        # Generation kwargs
        gen_kwargs = {
            **inputs,
            "max_new_tokens": self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": self.do_sample,
            "streamer": streamer,
        }
        # Only include sampling parameters when do_sample=True
        if self.do_sample:
            gen_kwargs.update({
                "temperature": self.temperature,
                "top_p": self.top_p,
            })
        if hasattr(tokenizer, "eos_token_id"):
            gen_kwargs.update({
                "eos_token_id": tokenizer.eos_token_id,
                "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
            })
        
        # Generate in background thread
        loop = asyncio.get_event_loop()
        async with self._gen_lock:
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
        info = {
            "model_name": self.model_name,
            "model_path": str(self.model_path) if self.model_path else None,
            "use_local_model": self.use_local_model,
            "device": self.device,
            "quantization": {
                "4bit": self.load_in_4bit and self.device == "cuda",
                "8bit": self.load_in_8bit and self.device == "cuda",
            },
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "vocab_size": len(self.processor.tokenizer) if self.processor and hasattr(self.processor, "tokenizer") else None,
            "is_loaded": self._model is not None,
        }
        
        # Add memory info if CUDA
        if self.device == "cuda" and torch.cuda.is_available() and self._model:
            info["gpu_memory_gb"] = torch.cuda.memory_allocated() / 1e9
        
        return info
