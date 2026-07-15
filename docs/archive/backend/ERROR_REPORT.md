# Backend Error Report

**Generated:** 2026-01-20  
**Source:** `backend-dev.log`

## Critical Issue: SQL Syntax Error in Vector Search

### Summary
The chat/stream endpoint fails when performing semantic search due to a PostgreSQL syntax error with pgvector parameter binding when using asyncpg driver.

### Error Details

**Error Type:** `sqlalchemy.exc.ProgrammingError`  
**Root Cause:** `asyncpg.exceptions.PostgresSyntaxError: syntax error at or near ":"`

**Location:**
- File: `backend/app/services/context/retriever.py`
- Line: 267
- Method: `_semantic_search()`
- Function: `retrieve()` → `_semantic_search()`

**Trigger Endpoint:** `POST /api/v1/chat/stream?patient_id=1&question=hey`

### Problematic SQL Query

```sql
SELECT 
    id,
    patient_id,
    content,
    source_type,
    source_id,
    context_date,
    chunk_index,
    page_number,
    1 - (embedding <=> :query_embedding::vector) as similarity
FROM memory_chunks
WHERE is_indexed = true
AND patient_id = $1
ORDER BY similarity DESC LIMIT $2
```

### Root Cause Analysis

The issue is with the parameter binding syntax:
- `:query_embedding::vector` uses SQLAlchemy named parameter syntax (`:query_embedding`) combined with PostgreSQL type casting (`::vector`)
- When using `text()` SQL with asyncpg, the parameter binding doesn't properly handle the type cast
- asyncpg expects parameters to be bound separately from type casts
- The `::vector` cast applied directly to the parameter placeholder causes a syntax error

### Impact

**Severity:** 🔴 **CRITICAL**  
**Affected Functionality:**
- Chat streaming endpoint (`/api/v1/chat/stream`)
- RAG-based question answering
- Semantic search for context retrieval
- Any feature that uses vector similarity search

**User Impact:**
- Chat functionality completely broken
- Users cannot ask questions via the chat interface
- Context retrieval fails for all queries

### Technical Details

**Stack Trace Path:**
1. `app/api/chat.py:125` - `stream_ask()` endpoint
2. `app/services/llm/rag.py:235` - `stream_ask()` method
3. `app/services/context/engine.py:121` - `get_context()` method
4. `app/services/context/retriever.py:127` - `retrieve()` method
5. `app/services/context/retriever.py:267` - `_semantic_search()` method ← **FAILURE POINT**

**Database Driver:** asyncpg (async PostgreSQL driver)  
**Vector Extension:** pgvector  
**SQLAlchemy:** Using `text()` for raw SQL execution

### Solution Required

The SQL query needs to be rewritten to properly handle parameter binding with asyncpg. The type cast should be applied separately from the parameter placeholder.

**Current (BROKEN):**
```python
1 - (embedding <=> :query_embedding::vector) as similarity
```

**Options to Fix:**
1. Cast the parameter value in Python before binding
2. Use PostgreSQL's `CAST()` function instead of `::` syntax
3. Use SQLAlchemy's vector type handling if available
4. Bind the embedding as a properly formatted vector string

### Related Components

**Files to Review:**
- `backend/app/services/context/retriever.py` (primary fix location)
- `backend/app/services/embeddings/search.py` (if similar queries exist)
- `backend/app/services/context/__init__.py` (dependencies)

**Dependencies:**
- asyncpg >= 0.30.0
- pgvector >= 0.3.0
- sqlalchemy[asyncio] >= 2.0.0

### Additional Observations

**Working Components:**
✅ Database connection successful  
✅ Authentication working  
✅ Patient/Records/Documents endpoints working  
✅ Embedding model loading successfully (MPS device)  
✅ Vector embeddings generation working

**Non-Issues:**
- Embedding generation is working (seen in logs: "Model loaded on mps")
- Database connection is healthy
- Authentication and authorization working correctly

### Next Steps

1. **IMMEDIATE:** Fix the SQL query parameter binding in `retriever.py`
2. Review other vector search queries for similar issues
3. Add integration tests for vector search functionality
4. Consider adding SQL query validation in development mode

---

## Fix Applied

**Files Modified:**
1. `backend/app/services/context/retriever.py` - Line 241
2. `backend/app/services/embeddings/search.py` - Lines 125, 128, 248

**Solution:**
Changed from PostgreSQL `::` type cast syntax to `CAST()` function:
- **Before:** `:query_embedding::vector`
- **After:** `CAST(:query_embedding AS vector)`

This syntax is compatible with asyncpg's parameter binding when using SQLAlchemy's `text()` function.

**Reason:**
asyncpg's prepared statement parser doesn't handle the `::` shorthand cast syntax correctly when it immediately follows a named parameter placeholder (`:param_name`). Using the standard SQL `CAST()` function ensures proper parameter binding.

## Issue Status

- [x] Identified
- [x] Root cause analyzed
- [x] Fix implemented
- [ ] Tested
- [ ] Verified in production
