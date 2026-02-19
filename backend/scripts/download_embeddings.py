"""Pre-download embeddings model for offline use.

Run this script before deploying to production to ensure
the embeddings model is cached locally.

Usage:
    uv run python scripts/download_embeddings.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))


def main():
    """Download embeddings model to cache."""
    from sentence_transformers import SentenceTransformer

    from app.config import settings

    model_name = settings.embedding_model
    cache_dir = settings.hf_cache_dir or Path.home() / ".cache" / "huggingface" / "hub"

    print(f"Downloading {model_name}...")
    print(f"Cache directory: {cache_dir}")

    try:
        cache_kwargs = {}
        if cache_dir:
            cache_kwargs["cache_folder"] = str(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)

        model = SentenceTransformer(model_name, **cache_kwargs)
        print("✅ Model downloaded successfully!")
        print(f"   Model: {model_name}")
        print(f"   Dimension: {model.get_sentence_embedding_dimension()}")
        print(f"   Cache location: {cache_dir}")

        # Test embedding generation
        test_text = "Test embedding"
        embedding = model.encode(test_text)
        print(f"   Test embedding generated: shape={embedding.shape}")

    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        print("\nTroubleshooting:")
        print("1. Check internet connection")
        print("2. Verify HF_TOKEN is set if model requires authentication")
        print("3. Check disk space in cache directory")
        sys.exit(1)


if __name__ == "__main__":
    main()
