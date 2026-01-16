-- Initialize PostgreSQL database with pgvector extension
-- This script runs automatically when the container starts

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

GRANT ALL PRIVILEGES ON DATABASE medmemory TO medmemory;

DO $$
BEGIN
    RAISE NOTICE 'MedMemory database initialized with pgvector extension';
END $$;
