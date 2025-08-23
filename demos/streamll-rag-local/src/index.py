#!/usr/bin/env python3
"""
Document indexing script using LlamaIndex + pgvector.

This script loads markdown documents from the data/ directory,
creates embeddings using OpenAI, and stores them in pgvector
for similarity search.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path to import streamll
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

# Load environment variables
load_dotenv()


def setup_llama_index():
    """Configure LlamaIndex settings."""
    # Set up Gemini embeddings with reduced dimensions
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="gemini-embedding-001",  # Using the latest model
        api_key=os.getenv("GEMINI_API_KEY"),
        embed_batch_size=100,
        # Try to configure for 768 dimensions (pgvector limit is 2000 for ivfflat)
    )



def create_vector_store():
    """Create pgvector store connection."""
    vector_store = PGVectorStore.from_params(
        database=os.getenv("DATABASE_NAME", "streamll_rag"),
        host=os.getenv("DATABASE_HOST", "localhost"),
        password=os.getenv("DATABASE_PASSWORD", "streamll_demo"),
        port=os.getenv("DATABASE_PORT", "5432"),
        user=os.getenv("DATABASE_USER", "streamll"),
        table_name="documents",
        embed_dim=3072,  # Gemini embedding dimension
    )

    return vector_store


def load_documents():
    """Load documents from data directory."""
    data_dir = Path(__file__).parent.parent / "data"

    if not data_dir.exists():
        sys.exit(1)

    # Load markdown documents
    reader = SimpleDirectoryReader(input_dir=str(data_dir), required_exts=[".md"])

    documents = reader.load_data()

    # Print document info
    for doc in documents:
        filename = Path(doc.metadata.get("file_name", "unknown")).stem
        preview = doc.text[:100].replace("\n", " ")
        print(f"Document: {filename}, Preview: {preview}")

    return documents


def index_documents():
    """Main indexing pipeline."""

    # Setup
    setup_llama_index()
    vector_store = create_vector_store()
    documents = load_documents()

    # Create storage context
    storage_context = StorageContext.from_defaults(vector_store=vector_store)


    # Create vector index (this will generate embeddings and store them)
    index = VectorStoreIndex.from_documents(
        documents=documents, storage_context=storage_context, show_progress=True
    )


    return index


def test_retrieval(index):
    """Test document retrieval."""

    test_queries = [
        "How does StreamLL integrate with DSPy?",
        "What are the production resilience features?",
        "Tell me about circuit breaker patterns",
    ]

    retriever = index.as_retriever(similarity_top_k=2)

    for query in test_queries:
        nodes = retriever.retrieve(query)

        for i, node in enumerate(nodes, 1):
            score = getattr(node, "score", "N/A")
            filename = Path(node.metadata.get("file_name", "unknown")).stem
            preview = node.text[:150].replace("\n", " ")
            print(f"Result {i}: {filename} (score: {score}), Preview: {preview}")


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit(1)

    try:
        # Index documents
        index = index_documents()

        # Test retrieval
        test_retrieval(index)


    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
