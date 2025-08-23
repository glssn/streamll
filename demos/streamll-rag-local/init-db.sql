-- Initialize pgvector extension for vector embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Create a table for document embeddings
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(3072),  -- Gemini gemini-embedding-001 size
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Note: Vector index skipped due to 2000 dimension limit in pgvector
-- For production, consider using dimension reduction or different embedding model
-- CREATE INDEX documents_embedding_idx ON documents USING hnsw (embedding vector_cosine_ops);