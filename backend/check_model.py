#!/usr/bin/env python3
"""Quick check if MedGemma model can be loaded."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import torch
from transformers import AutoTokenizer

print("🔍 Checking MedGemma-4B-IT Model Status")
print("=" * 50)

# Check device
print("\n📱 Device Info:")
print(f"   PyTorch: {torch.__version__}")
print(f"   CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   GPU: {torch.cuda.get_device_name(0)}")
print(f"   MPS: {torch.backends.mps.is_available()}")

# Check tokenizer
print("\n🧪 Testing Tokenizer:")
try:
    tokenizer = AutoTokenizer.from_pretrained(
        "google/medgemma-4b-it",
        trust_remote_code=True,
    )
    print("   ✅ Tokenizer loaded successfully")
    print(f"   Vocab size: {len(tokenizer)}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    sys.exit(1)

# Check model cache
print("\n📦 Model Cache:")
from transformers.utils import TRANSFORMERS_CACHE
cache_dir = Path.home() / ".cache" / "huggingface" / "transformers"
model_cache = cache_dir / "google--medgemma-4b-it"
if model_cache.exists():
    size_gb = sum(f.stat().st_size for f in model_cache.rglob("*") if f.is_file()) / 1e9
    print(f"   ✅ Model cached: {size_gb:.2f} GB")
else:
    print("   ⚠️  Model not cached (will download on first load)")

print("\n" + "=" * 50)
print("✅ Basic checks passed!")
print("\nTo test full model loading, run:")
print("   python test_model.py")
print("\nOr start the API and check:")
print("   GET /api/v1/chat/llm/info")
