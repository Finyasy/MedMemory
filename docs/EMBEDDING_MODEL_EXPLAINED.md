# How `all-MiniLM-L6-v2` Functions in MedMemory

## Overview

`all-MiniLM-L6-v2` is a **SentenceTransformer** model that converts text into **vector embeddings** (384-dimensional arrays of numbers). These embeddings enable **semantic search** - finding documents by meaning, not just keywords.

## What is an Embedding?

An embedding is a numerical representation of text that captures its **semantic meaning**:

```
Text: "Patient has high blood pressure"
↓
Embedding: [0.23, -0.45, 0.67, ..., 0.12]  (384 numbers)
```

**Key Property**: Similar texts have similar embeddings. This means:
- "high blood pressure" ≈ "hypertension" (similar vectors)
- "blood pressure" ≠ "blood sugar" (different vectors)

## How It Works in Your Project

### 1. **Model Loading** (On Backend Startup)

```python
# Location: backend/app/services/embeddings/embedding.py

# When backend starts, this loads the model:
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu/mps/cuda")
# Log: "INFO sentence_transformers.SentenceTransformer Load pretrained SentenceTransformer: all-MiniLM-L6-v2"
```

**What happens:**
- Downloads model from HuggingFace (if not cached)
- Loads into memory (~80MB)
- Runs on CPU, MPS (Apple Silicon), or CUDA (GPU)
- Singleton pattern: loaded once, reused everywhere

### 2. **Document Processing** (When Documents Are Uploaded)

```
Document Upload → Text Extraction → Chunking → Embedding Generation → Storage
```

**Step-by-step:**

1. **Text Extraction**: Document text is extracted (OCR, PDF parsing, etc.)
2. **Chunking**: Text is split into chunks (~500 characters each)
3. **Embedding**: Each chunk is converted to a 384-dimensional vector
4. **Storage**: Embeddings stored in PostgreSQL with `pgvector` extension

**Code Flow:**
```python
# backend/app/services/embeddings/indexing.py

# For each text chunk:
embedding = embedding_service.embed_text(chunk_content)
# Result: [0.23, -0.45, 0.67, ..., 0.12] (384 numbers)

# Stored in database:
memory_chunk.embedding = embedding  # Vector(384) column
memory_chunk.is_indexed = True
```

### 3. **Semantic Search** (When User Asks Questions)

```
User Question → Query Embedding → Vector Search → Relevant Chunks → RAG Response
```

**Step-by-step:**

1. **User asks**: "What medications is the patient taking?"
2. **Query Embedding**: Question converted to embedding vector
3. **Vector Search**: PostgreSQL finds chunks with similar embeddings
4. **Ranking**: Results sorted by similarity score (0-1)
5. **Context Building**: Top chunks sent to MedGemma for answer generation

**Code Flow:**
```python
# backend/app/services/context/retriever.py

# 1. Generate query embedding
query_embedding = await embedding_service.embed_query_async("What medications...")
# Result: [0.12, -0.34, 0.56, ..., 0.78] (384 numbers)

# 2. PostgreSQL vector search (using pgvector)
sql = """
    SELECT content, 
           1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
    FROM memory_chunks
    WHERE patient_id = :patient_id
      AND is_indexed = true
    ORDER BY similarity DESC
    LIMIT 10
"""
# <=> is cosine distance operator in pgvector
# similarity = 1 means identical, 0 means completely different
```

## Technical Details

### Model Specifications

- **Name**: `all-MiniLM-L6-v2`
- **Dimensions**: 384 (each embedding is 384 numbers)
- **Size**: ~80MB
- **Speed**: Fast (optimized for production)
- **Quality**: Good balance of speed and accuracy

### Why This Model?

1. **Fast**: Processes text quickly (important for real-time search)
2. **Small**: Fits in memory easily
3. **Good Quality**: Captures semantic meaning well
4. **Popular**: Well-tested, widely used

### Embedding Process

```python
# Input text
text = "Patient has diabetes and takes metformin 500mg twice daily"

# Model encodes it
embedding = model.encode(text, normalize_embeddings=True)
# normalize_embeddings=True means L2 normalization
# This makes cosine similarity = dot product (faster)

# Output: 384-dimensional vector
# [0.123, -0.456, 0.789, ..., 0.234]
```

### Similarity Calculation

```python
# Cosine similarity between two embeddings
similarity = dot_product(embedding1, embedding2)
# For normalized vectors, this is just: sum(a[i] * b[i])

# Example:
query_embedding = [0.1, 0.2, 0.3, ...]
chunk_embedding = [0.15, 0.18, 0.32, ...]
similarity = 0.85  # Very similar! (0-1 scale)
```

## Integration Points in Your Project

### 1. **Document Indexing** (`backend/app/services/embeddings/indexing.py`)

```python
# When documents are processed:
chunks = ["chunk 1 text", "chunk 2 text", ...]
embeddings = embedding_service.embed_texts(chunks)
# Stores embeddings in memory_chunks.embedding column
```

### 2. **Semantic Search** (`backend/app/services/context/retriever.py`)

```python
# When user asks a question:
query = "What medications is the patient taking?"
query_embedding = await embedding_service.embed_query_async(query)
# Searches for similar chunks using pgvector
```

### 3. **RAG Pipeline** (`backend/app/services/llm/rag.py`)

```python
# Full flow:
1. User question → Query embedding
2. Vector search → Find relevant chunks
3. Build context from chunks
4. Send to MedGemma → Generate answer
```

## Database Storage

### PostgreSQL + pgvector

```sql
-- Memory chunks table
CREATE TABLE memory_chunks (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(384),  -- 384-dimensional vector
    is_indexed BOOLEAN,
    ...
);

-- Vector similarity search
SELECT content, 
       1 - (embedding <=> query_vector) as similarity
FROM memory_chunks
WHERE patient_id = 123
ORDER BY similarity DESC;
```

**Why pgvector?**
- Fast vector similarity search
- Native PostgreSQL integration
- Efficient indexing (HNSW or IVFFlat)

## Performance Characteristics

### Speed
- **Embedding generation**: ~1-5ms per chunk (CPU)
- **Vector search**: ~10-50ms for 1000 chunks (with index)
- **Batch processing**: ~32 chunks at a time

### Memory
- **Model size**: ~80MB in RAM
- **Embedding size**: 384 floats = 1.5KB per chunk
- **1000 chunks**: ~1.5MB of embeddings

### Accuracy
- **Semantic matching**: Finds related concepts, not just keywords
- **Example**: "blood pressure" matches "hypertension", "BP", "systolic/diastolic"

## Why This Matters for Your Project

### Without Embeddings (Keyword Search Only)
```
User: "What medications is the patient taking?"
Search: Finds only exact matches for "medications", "taking"
Problem: Misses "patient is on metformin" or "prescribed insulin"
```

### With Embeddings (Semantic Search)
```
User: "What medications is the patient taking?"
Search: Finds "patient is on metformin", "prescribed insulin", 
        "current meds include...", etc.
Result: Much better context retrieval for RAG
```

## The Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    DOCUMENT UPLOAD                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Text Extraction (OCR/Vision/PDF)                │
│              "Patient has diabetes. Takes metformin..."      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Text Chunking                            │
│              ["Patient has diabetes.",                       │
│               "Takes metformin 500mg..."]                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         all-MiniLM-L6-v2 Embedding Generation               │
│              [0.23, -0.45, ...]  (384 dims)                 │
│              [0.12, 0.34, ...]   (384 dims)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL + pgvector Storage                   │
│              memory_chunks.embedding = vector(384)          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    USER QUESTION                            │
│              "What medications is the patient taking?"      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         all-MiniLM-L6-v2 Query Embedding                    │
│              [0.15, -0.38, ...]  (384 dims)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Vector Similarity Search             │
│              ORDER BY similarity DESC                        │
│              Returns: Top 10 most similar chunks             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Context Building + MedGemma RAG                 │
│              Generates answer using retrieved chunks         │
└─────────────────────────────────────────────────────────────┘
```

## Key Takeaways

1. **Purpose**: Converts text → numbers for semantic search
2. **When Used**: 
   - Document indexing (chunks → embeddings)
   - Query processing (questions → embeddings)
3. **Storage**: PostgreSQL with pgvector extension
4. **Result**: Enables finding relevant information by meaning, not just keywords
5. **Performance**: Fast, efficient, production-ready

## Configuration

```python
# backend/app/config.py
embedding_model: str = "all-MiniLM-L6-v2"  # Model name
embedding_dimension: int = 384              # Vector size
```

## Alternative Models (If Needed)

- **`all-mpnet-base-v2`**: 768 dims, slower, better quality
- **`multi-qa-MiniLM-L6-cos-v1`**: 384 dims, optimized for Q&A

## Summary

`all-MiniLM-L6-v2` is the **semantic search engine** of your RAG system. It:
- Converts text to numerical vectors
- Enables meaning-based search (not just keywords)
- Powers the "Summarize in chat" feature
- Makes your medical records searchable by concept

Without it, you'd only find exact keyword matches. With it, you find semantically related information, which is crucial for medical queries where terminology varies.
