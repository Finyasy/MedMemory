"""LLM service for MedGemma-1.5-4B-IT inference.

Handles model loading, tokenization, and text generation.
Optimized for MPS (Apple Silicon) and CUDA.
"""

import asyncio
import importlib.util
import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import torch
from PIL import Image
from transformers import (
    AutoProcessor,
    BitsAndBytesConfig,
    TextIteratorStreamer,
)

from app.config import settings

logger = logging.getLogger("medmemory")


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
    _mlx_model = None
    _mlx_tokenizer = None

    def __init__(
        self,
        model_name: str | None = None,
        model_path: Path | None = None,
        device: str | None = None,
        load_in_8bit: bool = False,
        load_in_4bit: bool | None = None,
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
            elif (
                not self.model_path.exists()
                and "app" in self.model_path.parts
                and "models" in self.model_path.parts
            ):
                candidate = (backend_dir / "models" / self.model_path.name).resolve()
                if candidate.exists():
                    self.model_path = candidate
            self.model_name = str(self.model_path)
            self.use_local_model = True
        elif settings.llm_model_path:
            self.model_path = Path(settings.llm_model_path)
            if not self.model_path.is_absolute():
                self.model_path = (backend_dir / self.model_path).resolve()
            elif (
                not self.model_path.exists()
                and "app" in self.model_path.parts
                and "models" in self.model_path.parts
            ):
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
        self.max_new_tokens = settings.llm_max_new_tokens
        self.temperature = settings.llm_temperature
        self.top_p = settings.llm_top_p
        self.top_k = settings.llm_top_k
        self.repetition_penalty = settings.llm_repetition_penalty
        # Sampling is configurable but defaults to deterministic for clinical QA.
        self.do_sample = settings.llm_do_sample
        # Prefer MLX text generation on Apple Silicon when configured and available.
        self.use_mlx_text_backend = bool(
            settings.llm_use_mlx and self.device == "mps"
        )
        self._mlx_disabled_reason: str | None = None
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

    def _resolve_mlx_model_name(self) -> str:
        """Resolve best MLX model source (prefer explicit quantized path)."""
        quantized_path = settings.llm_mlx_quantized_model_path
        if quantized_path:
            candidate = Path(quantized_path)
            if not candidate.is_absolute():
                backend_dir = Path(__file__).resolve().parents[3]
                candidate = (backend_dir / candidate).resolve()
            if candidate.exists() and candidate.is_dir() and any(
                (candidate / name).exists()
                for name in ["config.json", "model.safetensors", "weights.npz"]
            ):
                return str(candidate)

        if self.model_path and self.model_path.exists() and self.model_path.is_dir():
            return str(self.model_path)
        return self.model_name

    def _load_mlx_runtime(self) -> bool:
        """Lazy-load MLX text runtime; return False when unavailable."""
        if not self.use_mlx_text_backend:
            return False
        if self._mlx_model is not None and self._mlx_tokenizer is not None:
            return True
        if self._mlx_disabled_reason:
            return False

        try:
            from mlx_lm import load as mlx_load  # type: ignore[import-not-found]
        except Exception as exc:
            self._mlx_disabled_reason = str(exc)
            logger.warning(
                "MLX runtime unavailable; using Transformers backend instead: %s", exc
            )
            self.use_mlx_text_backend = False
            return False

        model_source = self._resolve_mlx_model_name()
        quant_bits = settings.llm_mlx_quantization_bits
        if quant_bits in {4, 8}:
            logger.info(
                "MLX text backend enabled (preferred quantization=%s-bit, source=%s)",
                quant_bits,
                model_source,
            )
        else:
            logger.info("MLX text backend enabled (source=%s)", model_source)

        try:
            model, tokenizer = mlx_load(model_source)
        except Exception as exc:
            self._mlx_disabled_reason = str(exc)
            logger.warning(
                "MLX model load failed; falling back to Transformers backend: %s",
                exc,
            )
            self.use_mlx_text_backend = False
            return False

        self._mlx_model = model
        self._mlx_tokenizer = tokenizer
        return True

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
        try:
            from transformers import AutoModelForImageTextToText as AutoVisionModel
        except Exception:  # pragma: no cover - version dependent fallback
            from transformers import AutoModelForVision2Seq as AutoVisionModel

        source = "local path" if self.use_local_model else "Hugging Face"
        logger.info("Loading LLM model from %s: %s", source, self.model_name)
        logger.info("Device: %s", self.device)

        dtype = self._pick_dtype()
        logger.info("DType: %s", dtype)

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
            logger.info("Using INT4 (4-bit) quantization with best practices")
            quant_cfg = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
            model_kwargs["quantization_config"] = quant_cfg
        elif self.load_in_8bit and self.device == "cuda":
            logger.info("Using INT8 (8-bit) quantization")
            quant_cfg = BitsAndBytesConfig(load_in_8bit=True)
            model_kwargs["quantization_config"] = quant_cfg
        elif (self.load_in_4bit or self.load_in_8bit) and self.device != "cuda":
            logger.warning("4-bit quantization requires CUDA. Skipping quantization.")

        # Load model
        try:
            model = AutoVisionModel.from_pretrained(
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
                logger.info("Model loaded successfully with quantization")
            else:
                logger.info("Model loaded successfully")

            # Show memory usage
            if self.device == "cuda" and torch.cuda.is_available():
                memory_gb = torch.cuda.memory_allocated() / 1e9
                logger.info("GPU memory used: %.2f GB", memory_gb)
            elif self.device == "mps":
                # MPS doesn't have direct memory reporting, but we can check model size
                param_count = sum(p.numel() for p in model.parameters())
                logger.info("Model parameters: %.2fB", param_count / 1e9)

            return model

        except ImportError as e:
            if "bitsandbytes" in str(e):
                raise ImportError(
                    "bitsandbytes is required for 4-bit quantization. "
                    "Install it with: pip install bitsandbytes"
                ) from e
            raise
        except Exception as e:
            logger.error("Error loading model: %s", e)
            if self.use_local_model:
                logger.error(
                    "Hint: Make sure the model is downloaded to: %s", self.model_path
                )
                logger.error("Run: python scripts/download_model.py")
            raise

    def _load_processor(self):
        """Load the processor from local path or Hugging Face.

        MedGemma uses AutoProcessor which handles both text and vision inputs.
        """
        logger.info("Loading processor for %s", self.model_name)

        processor_kwargs = {
            "trust_remote_code": True,
        }

        # Use local_files_only if loading from local path
        if self.use_local_model:
            processor_kwargs["local_files_only"] = True

        # Check if torchvision is available for fast processor
        if importlib.util.find_spec("torchvision") is not None:
            use_fast = True
            logger.debug("torchvision available, using fast processor")
        else:
            use_fast = False
            logger.info(
                "torchvision not available, using slow image processor (this is fine)"
            )

        processor = AutoProcessor.from_pretrained(
            self.model_name,
            use_fast=use_fast,  # Explicitly set based on torchvision availability
            **processor_kwargs,
        )

        logger.info("Processor loaded successfully")
        return processor

    async def generate(
        self,
        prompt: str,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
        do_sample: bool | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repetition_penalty: float | None = None,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
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
        if self.use_mlx_text_backend and self._load_mlx_runtime():
            return await self._generate_with_mlx(
                prompt=prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=do_sample,
                top_p=top_p,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )

        return await self._generate_with_transformers(
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=do_sample,
            top_p=top_p,
            top_k=top_k,
            repetition_penalty=repetition_penalty,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
        )

    async def _generate_with_transformers(
        self,
        *,
        prompt: str,
        max_new_tokens: int | None,
        temperature: float | None,
        do_sample: bool | None,
        top_p: float | None,
        top_k: int | None,
        repetition_penalty: float | None,
        system_prompt: str | None,
        conversation_history: list[dict] | None,
    ) -> LLMResponse:
        """Generate text using the Transformers runtime."""
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
        inputs = {
            k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()
        }

        input_tokens = inputs["input_ids"].shape[1] if "input_ids" in inputs else 0

        # Generation parameters
        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        effective_do_sample = self.do_sample if do_sample is None else do_sample
        effective_repetition_penalty = (
            self.repetition_penalty
            if repetition_penalty is None
            else repetition_penalty
        )
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_new_tokens,
            "repetition_penalty": effective_repetition_penalty,
            "do_sample": effective_do_sample,
        }
        # Only include sampling parameters when do_sample=True
        if effective_do_sample:
            gen_kwargs.update(
                {
                    "temperature": temperature or self.temperature,
                    "top_p": self.top_p if top_p is None else top_p,
                    "top_k": self.top_k if top_k is None else top_k,
                }
            )
        if tokenizer:
            gen_kwargs.update(
                {
                    "eos_token_id": tokenizer.eos_token_id,
                    "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
                }
            )

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
        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        if tokenizer:
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
        else:
            generated_text = self.processor.batch_decode(
                [generated_ids], skip_special_tokens=True
            )[0]

        output_tokens = max(int(seq.shape[0] - input_len), 0)
        generation_time = (time.time() - start_time) * 1000

        return LLMResponse(
            text=generated_text.strip(),
            tokens_generated=output_tokens,
            tokens_input=input_tokens,
            generation_time_ms=generation_time,
        )

    def _estimate_mlx_tokens(self, text: str) -> int:
        """Best-effort token count for MLX generation metadata."""
        tokenizer = self._mlx_tokenizer
        if tokenizer is None:
            return 0
        try:
            encoded = tokenizer.encode(text)
            return int(len(encoded))
        except Exception:
            pass
        try:
            if hasattr(tokenizer, "tokenize"):
                return int(len(tokenizer.tokenize(text)))
        except Exception:
            pass
        return 0

    async def _generate_with_mlx(
        self,
        *,
        prompt: str,
        max_new_tokens: int | None,
        temperature: float | None,
        do_sample: bool | None,
        top_p: float | None,
        system_prompt: str | None,
        conversation_history: list[dict] | None,
    ) -> LLMResponse:
        """Generate text using MLX runtime on Apple Silicon."""
        import time

        # Build full prompt (skip wrapping if prompt is already composed)
        if system_prompt is None and not conversation_history:
            full_prompt = prompt
        else:
            full_prompt = self._build_prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )

        effective_do_sample = self.do_sample if do_sample is None else do_sample
        effective_temperature = (
            temperature if temperature is not None else self.temperature
        )
        effective_top_p = self.top_p if top_p is None else top_p
        effective_top_k = self.top_k
        max_tokens = max_new_tokens or self.max_new_tokens

        start_time = time.time()
        from mlx_lm import generate as mlx_generate  # type: ignore[import-not-found]
        from mlx_lm.sample_utils import make_sampler  # type: ignore[import-not-found]

        def _mlx_generate() -> str:
            kwargs = {
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "verbose": False,
            }
            if effective_do_sample:
                sampler = make_sampler(
                    temp=effective_temperature,
                    top_p=effective_top_p,
                    top_k=effective_top_k,
                )
            else:
                sampler = make_sampler(temp=0.0)
            kwargs["sampler"] = sampler

            try:
                output = mlx_generate(self._mlx_model, self._mlx_tokenizer, **kwargs)
            except TypeError as exc:
                # Backward-compat fallback for older mlx-lm signatures.
                if "sampler" not in str(exc):
                    raise
                kwargs.pop("sampler", None)
                if effective_do_sample:
                    kwargs["temp"] = effective_temperature
                    kwargs["top_p"] = effective_top_p
                else:
                    kwargs["temp"] = 0.0
                output = mlx_generate(self._mlx_model, self._mlx_tokenizer, **kwargs)

            if isinstance(output, str):
                return output
            if hasattr(output, "text"):
                return str(output.text)
            if isinstance(output, dict):
                return str(
                    output.get("text")
                    or output.get("output")
                    or output.get("response")
                    or ""
                )
            return str(output)

        async with self._gen_lock:
            generated_text = await asyncio.get_event_loop().run_in_executor(
                None,
                _mlx_generate,
            )

        generation_time = (time.time() - start_time) * 1000
        input_tokens = self._estimate_mlx_tokens(full_prompt)
        output_tokens = self._estimate_mlx_tokens(generated_text)

        return LLMResponse(
            text=(generated_text or "").strip(),
            tokens_generated=output_tokens,
            tokens_input=input_tokens,
            generation_time_ms=generation_time,
        )

    async def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        max_new_tokens: int | None = None,
        min_new_tokens: int | None = None,
        temperature: float | None = None,
        do_sample: bool | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repetition_penalty: float | None = None,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate text from a prompt and image input."""
        import time

        start_time = time.time()

        # Load and convert image first
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Build messages with image in the official MedGemma format
        # For multimodal, ALL message contents must be list-of-dicts format
        messages = []
        if system_prompt:
            # System prompt as text-only content list
            messages.append(
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]}
            )
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                # Convert string content to list format
                messages.append(
                    {"role": role, "content": [{"type": "text", "text": content}]}
                )

        # User message with image and text (official MedGemma format)
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        )

        # Use processor.apply_chat_template directly (not tokenizer)
        # This is the official MedGemma 1.5 approach
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )

        # Move inputs to model device with proper dtype
        model_device = next(self.model.parameters()).device
        model_dtype = next(self.model.parameters()).dtype
        inputs = {
            k: v.to(
                model_device,
                dtype=model_dtype
                if v.dtype in (torch.float32, torch.float16, torch.bfloat16)
                else None,
            )
            if hasattr(v, "to")
            else v
            for k, v in inputs.items()
        }
        input_tokens = inputs["input_ids"].shape[-1] if "input_ids" in inputs else 0
        self._validate_multimodal_inputs(
            inputs=inputs,
            expected_image_count=1,
            mode="single-image",
        )

        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        effective_do_sample = self.do_sample if do_sample is None else do_sample
        effective_repetition_penalty = (
            self.repetition_penalty
            if repetition_penalty is None
            else repetition_penalty
        )
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_new_tokens,
            "repetition_penalty": effective_repetition_penalty,
            "do_sample": effective_do_sample,
        }
        if min_new_tokens is not None:
            gen_kwargs["min_new_tokens"] = min_new_tokens
        if effective_do_sample:
            gen_kwargs.update(
                {
                    "temperature": temperature or self.temperature,
                    "top_p": self.top_p if top_p is None else top_p,
                    "top_k": self.top_k if top_k is None else top_k,
                }
            )
        if tokenizer:
            gen_kwargs.update(
                {
                    "eos_token_id": tokenizer.eos_token_id,
                    "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
                }
            )

        loop = asyncio.get_event_loop()

        def _generate():
            with torch.inference_mode():
                return self.model.generate(**inputs, **gen_kwargs)

        async with self._gen_lock:
            outputs = await loop.run_in_executor(None, _generate)

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

        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        if tokenizer:
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
        else:
            generated_text = self.processor.batch_decode(
                [generated_ids], skip_special_tokens=True
            )[0]

        output_tokens = max(int(seq.shape[0] - input_len), 0)
        generation_time = (time.time() - start_time) * 1000

        return LLMResponse(
            text=generated_text.strip(),
            tokens_generated=output_tokens,
            tokens_input=input_tokens,
            generation_time_ms=generation_time,
        )

    async def generate_with_images(
        self,
        prompt: str,
        images_bytes: list[bytes],
        max_new_tokens: int | None = None,
        min_new_tokens: int | None = None,
        temperature: float | None = None,
        do_sample: bool | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repetition_penalty: float | None = None,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate text from a prompt and multiple image inputs."""
        import time

        start_time = time.time()

        if not images_bytes:
            raise ValueError("At least one image is required.")

        full_prompt = None
        if system_prompt is None and not conversation_history:
            full_prompt = prompt
        else:
            full_prompt = self._build_prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )

        images = [
            Image.open(io.BytesIO(payload)).convert("RGB") for payload in images_bytes
        ]

        if hasattr(self.processor, "tokenizer") and hasattr(
            self.processor.tokenizer, "apply_chat_template"
        ):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if conversation_history:
                for turn in conversation_history:
                    role = turn.get("role", "user")
                    content = turn.get("content", "")
                    messages.append({"role": role, "content": content})
            content = [{"type": "image"} for _ in images]
            content.append({"type": "text", "text": prompt})
            messages.append({"role": "user", "content": content})
            full_prompt = self.processor.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            image_token = self._ensure_image_token(full_prompt)
            full_prompt = f"{image_token} " * len(images) + full_prompt

        inputs = self.processor(
            text=full_prompt,
            images=images,
            return_tensors="pt",
        )

        model_device = next(self.model.parameters()).device
        inputs = {
            k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()
        }

        input_tokens = inputs["input_ids"].shape[1] if "input_ids" in inputs else 0
        self._validate_multimodal_inputs(
            inputs=inputs,
            expected_image_count=len(images),
            mode="multi-image",
        )
        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        effective_do_sample = self.do_sample if do_sample is None else do_sample
        effective_repetition_penalty = (
            self.repetition_penalty
            if repetition_penalty is None
            else repetition_penalty
        )
        gen_kwargs = {
            "max_new_tokens": max_new_tokens or self.max_new_tokens,
            "repetition_penalty": effective_repetition_penalty,
            "do_sample": effective_do_sample,
        }
        if min_new_tokens is not None:
            gen_kwargs["min_new_tokens"] = min_new_tokens
        if effective_do_sample:
            gen_kwargs.update(
                {
                    "temperature": temperature or self.temperature,
                    "top_p": self.top_p if top_p is None else top_p,
                    "top_k": self.top_k if top_k is None else top_k,
                }
            )
        if tokenizer:
            gen_kwargs.update(
                {
                    "eos_token_id": tokenizer.eos_token_id,
                    "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
                }
            )

        loop = asyncio.get_event_loop()

        def _generate():
            with torch.inference_mode():
                return self.model.generate(**inputs, **gen_kwargs)

        async with self._gen_lock:
            outputs = await loop.run_in_executor(None, _generate)

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

        if tokenizer:
            generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
        else:
            generated_text = self.processor.batch_decode(
                [generated_ids], skip_special_tokens=True
            )[0]

        output_tokens = max(int(seq.shape[0] - input_len), 0)
        generation_time = (time.time() - start_time) * 1000

        return LLMResponse(
            text=generated_text.strip(),
            tokens_generated=output_tokens,
            tokens_input=input_tokens,
            generation_time_ms=generation_time,
        )

    def _ensure_image_token(self, prompt: str) -> str:
        """Ensure the prompt includes a model-specific image token."""
        image_token = getattr(self.processor, "image_token", None)
        if not image_token and hasattr(self.processor, "tokenizer"):
            image_token = getattr(self.processor.tokenizer, "image_token", None)
        if not image_token:
            image_token = "<image>"
        if image_token in prompt:
            return prompt
        return f"{image_token}\n{prompt}"

    def _validate_multimodal_inputs(
        self,
        *,
        inputs: dict,
        expected_image_count: int,
        mode: str,
    ) -> None:
        """Sanity-check that image tensors are present and plausible."""
        pixel_values = inputs.get("pixel_values")
        if pixel_values is None:
            raise RuntimeError(
                "Multimodal input is missing pixel_values. "
                "Aborting to avoid text-only generation fallback."
            )

        pixel_shape = tuple(int(dim) for dim in getattr(pixel_values, "shape", ()))
        inferred_image_count = 0
        if len(pixel_shape) >= 5:
            inferred_image_count = pixel_shape[1]
        elif len(pixel_shape) >= 4:
            inferred_image_count = pixel_shape[0]

        image_token_count: int | None = None
        tokenizer = self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        if tokenizer is not None and "input_ids" in inputs:
            image_token_id = getattr(tokenizer, "image_token_id", None)
            if image_token_id is None:
                image_token = getattr(tokenizer, "image_token", None)
                if image_token:
                    try:
                        image_token_id = tokenizer.convert_tokens_to_ids(image_token)
                    except Exception:
                        image_token_id = None
            if image_token_id is not None and image_token_id >= 0:
                token_matches = inputs["input_ids"] == image_token_id
                image_token_count = int(token_matches.sum().item())

        logger.info(
            "Multimodal input check mode=%s expected_images=%s pixel_shape=%s inferred_images=%s image_tokens=%s",
            mode,
            expected_image_count,
            pixel_shape,
            inferred_image_count if inferred_image_count else "unknown",
            image_token_count if image_token_count is not None else "unknown",
        )

        if inferred_image_count and inferred_image_count < expected_image_count:
            raise RuntimeError(
                "Model received fewer image tensors than expected: "
                f"expected={expected_image_count}, inferred={inferred_image_count}"
            )

    def _build_prompt(
        self,
        prompt: str,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Build the full prompt with system message and history."""
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role not in {"user", "assistant", "system"}:
                    role = "user"
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})

        tokenizer = (
            self.processor.tokenizer if hasattr(self.processor, "tokenizer") else None
        )
        if (
            tokenizer
            and hasattr(tokenizer, "apply_chat_template")
            and getattr(tokenizer, "chat_template", None)
        ):
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                pass

        parts = []
        if system_prompt:
            parts.append(f"System: {system_prompt}\n")
        if conversation_history:
            for turn in conversation_history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "user":
                    parts.append(f"User: {content}\n")
                elif role == "assistant":
                    parts.append(f"Assistant: {content}\n")
        parts.append(f"User: {prompt}\n")
        parts.append("Assistant:")
        return "".join(parts)

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        conversation_history: list[dict] | None = None,
        temperature: float | None = None,
        do_sample: bool | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
    ):
        """Stream generated text token by token.

        Yields:
            Generated text chunks
        """
        if self.use_mlx_text_backend and self._load_mlx_runtime():
            response = await self._generate_with_mlx(
                prompt=prompt,
                max_new_tokens=self.max_new_tokens,
                temperature=temperature,
                do_sample=do_sample,
                top_p=top_p,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
            )
            if response.text:
                yield response.text
            return

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
        inputs = {
            k: v.to(model_device) if hasattr(v, "to") else v for k, v in inputs.items()
        }

        # Create streamer (using processor's tokenizer)
        tokenizer = (
            self.processor.tokenizer
            if hasattr(self.processor, "tokenizer")
            else self.processor
        )
        streamer = TextIteratorStreamer(
            tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        # Generation kwargs
        effective_do_sample = self.do_sample if do_sample is None else do_sample
        gen_kwargs = {
            **inputs,
            "max_new_tokens": self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
            "do_sample": effective_do_sample,
            "streamer": streamer,
        }
        # Only include sampling parameters when do_sample=True
        if effective_do_sample:
            gen_kwargs.update(
                {
                    "temperature": self.temperature if temperature is None else temperature,
                    "top_p": self.top_p if top_p is None else top_p,
                    "top_k": self.top_k if top_k is None else top_k,
                }
            )
        if hasattr(tokenizer, "eos_token_id"):
            gen_kwargs.update(
                {
                    "eos_token_id": tokenizer.eos_token_id,
                    "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
                }
            )

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
        tokenizer = None
        if hasattr(self, "_tokenizer") and self._tokenizer is not None:
            tokenizer = self._tokenizer
        elif self._processor is not None and hasattr(self._processor, "tokenizer"):
            tokenizer = self._processor.tokenizer
        elif self._processor is not None:
            tokenizer = self._processor

        info = {
            "model_name": self.model_name,
            "model_path": str(self.model_path) if self.model_path else None,
            "use_local_model": self.use_local_model,
            "device": self.device,
            "runtime": (
                "mlx"
                if self.use_mlx_text_backend and self._mlx_model is not None
                else "transformers"
            ),
            "quantization": {
                "4bit": self.load_in_4bit and self.device == "cuda",
                "8bit": self.load_in_8bit and self.device == "cuda",
                "mlx_quantization_bits": settings.llm_mlx_quantization_bits
                if self.use_mlx_text_backend
                else 0,
            },
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "vocab_size": len(tokenizer) if tokenizer is not None else None,
            "is_loaded": self._model is not None,
        }

        # Add memory info if CUDA
        if self.device == "cuda" and torch.cuda.is_available() and self._model:
            info["gpu_memory_gb"] = torch.cuda.memory_allocated() / 1e9

        return info
