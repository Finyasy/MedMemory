#!/usr/bin/env python3
"""Test script to verify MedGemma-4B-IT model is working locally."""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def check_device():
    """Check available devices."""
    print("🔍 Checking available devices...")
    print(f"   PyTorch version: {torch.__version__}")
    print(f"   CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA device: {torch.cuda.get_device_name(0)}")
        print(f"   CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    print(f"   MPS available: {torch.backends.mps.is_available()}")
    print()


def check_model_files(model_name: str = "google/medgemma-4b-it"):
    """Check if model files exist in cache."""
    print(f"🔍 Checking for model: {model_name}")
    
    from transformers.utils import TRANSFORMERS_CACHE
    
    cache_dir = Path.home() / ".cache" / "huggingface" / "transformers"
    print(f"   HuggingFace cache: {cache_dir}")
    
    # Check if model directory exists
    model_cache = cache_dir / model_name.replace("/", "--")
    if model_cache.exists():
        print(f"   ✅ Model cache found: {model_cache}")
        size_gb = sum(f.stat().st_size for f in model_cache.rglob("*") if f.is_file()) / 1e9
        print(f"   📦 Cache size: {size_gb:.2f} GB")
    else:
        print(f"   ⚠️  Model cache not found (will download on first load)")
    print()


def test_tokenizer(model_name: str = "google/medgemma-4b-it"):
    """Test tokenizer loading."""
    print("🧪 Testing tokenizer loading...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        print(f"   ✅ Tokenizer loaded successfully")
        print(f"   📊 Vocab size: {len(tokenizer)}")
        
        # Test tokenization
        test_text = "What medications is the patient taking?"
        tokens = tokenizer(test_text, return_tensors="pt")
        print(f"   ✅ Tokenization test: {len(tokens['input_ids'][0])} tokens")
        return tokenizer
    except Exception as e:
        print(f"   ❌ Error loading tokenizer: {e}")
        return None


def test_model_loading(model_name: str = "google/medgemma-4b-it", load_quantized: bool = False):
    """Test model loading."""
    print("🧪 Testing model loading...")
    
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    
    print(f"   Device: {device}")
    
    try:
        model_kwargs = {
            "torch_dtype": torch.float16 if device != "cpu" else torch.float32,
            "trust_remote_code": True,
        }
        
        if device != "cpu":
            model_kwargs["device_map"] = "auto"
        
        if load_quantized:
            print("   ⚠️  Loading with 8-bit quantization (memory efficient)")
            try:
                from transformers import BitsAndBytesConfig
                model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            except ImportError:
                print("   ⚠️  bitsandbytes not installed, loading full precision")
        
        print("   ⏳ Loading model (this may take a while on first run)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            **model_kwargs,
        )
        
        if device == "cpu":
            model = model.to(device)
        
        model.eval()
        print(f"   ✅ Model loaded successfully")
        
        # Get model info
        num_params = sum(p.numel() for p in model.parameters())
        print(f"   📊 Parameters: {num_params / 1e9:.2f}B")
        
        if device == "cuda":
            memory_allocated = torch.cuda.memory_allocated() / 1e9
            print(f"   💾 GPU memory used: {memory_allocated:.2f} GB")
        
        return model
    except Exception as e:
        print(f"   ❌ Error loading model: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_inference(model, tokenizer, device: str = "cpu"):
    """Test model inference."""
    print("🧪 Testing inference...")
    
    prompt = "User: What is diabetes?\nAssistant:"
    
    try:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        print("   ⏳ Generating response...")
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        
        response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print(f"   ✅ Inference successful!")
        print(f"   📝 Response: {response[:200]}...")
        return True
    except Exception as e:
        print(f"   ❌ Error during inference: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_llm_service():
    """Test the LLMService class."""
    print("🧪 Testing LLMService class...")
    
    try:
        from app.services.llm.model import LLMService
        
        service = LLMService()
        print(f"   ✅ LLMService initialized")
        print(f"   📋 Model: {service.model_name}")
        print(f"   📋 Device: {service.device}")
        
        # Test lazy loading
        print("   ⏳ Loading model (lazy load)...")
        tokenizer = service.tokenizer
        model = service.model
        
        print("   ✅ Model and tokenizer loaded via service")
        
        # Test generation
        print("   ⏳ Testing generation...")
        response = await service.generate(
            prompt="What is hypertension?",
            max_new_tokens=50,
        )
        
        print(f"   ✅ Generation successful!")
        print(f"   📝 Response: {response.text[:200]}...")
        print(f"   ⏱️  Generation time: {response.generation_time_ms:.0f}ms")
        print(f"   🎯 Tokens: {response.tokens_generated} generated, {response.tokens_input} input")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing LLMService: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🧠 MedGemma-4B-IT Model Test")
    print("=" * 60)
    print()
    
    model_name = "google/medgemma-4b-it"
    
    # Check device
    check_device()
    
    # Check model files
    check_model_files(model_name)
    
    # Test tokenizer
    tokenizer = test_tokenizer(model_name)
    if not tokenizer:
        print("❌ Tokenizer test failed. Cannot continue.")
        return
    
    print()
    
    # Ask user if they want to test full model loading
    print("⚠️  Model loading will download ~8GB if not cached.")
    print("   This may take a while and use significant memory.")
    print()
    
    try:
        response = input("Load full model for testing? (y/n): ").strip().lower()
        if response != 'y':
            print("⏭️  Skipping full model test. Use LLMService for lazy loading.")
            return
    except KeyboardInterrupt:
        print("\n⏭️  Skipping full model test.")
        return
    
    print()
    
    # Test model loading (without quantization first)
    model = test_model_loading(model_name, load_quantized=False)
    if not model:
        print("❌ Model loading failed.")
        return
    
    print()
    
    # Test inference
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    
    inference_ok = await test_inference(model, tokenizer, device)
    
    print()
    print("=" * 60)
    
    if inference_ok:
        print("✅ All tests passed! Model is working locally.")
    else:
        print("❌ Inference test failed.")
    
    print()
    print("🧪 Testing LLMService integration...")
    print()
    
    service_ok = await test_llm_service()
    
    print()
    print("=" * 60)
    
    if service_ok:
        print("✅ LLMService is working correctly!")
    else:
        print("❌ LLMService test failed.")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
