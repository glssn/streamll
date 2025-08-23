#!/usr/bin/env python3
"""
Real-world RAG demo using DSPy + StreamLL monitoring.

This demo shows StreamLL in action with:
- DSPy for LLM orchestration
- pgvector for document retrieval
- TerminalSink for beautiful development output
- RedisSink for production event streaming
- Real-time monitoring of LLM calls and tool usage
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path to import streamll
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import dspy
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore

import streamll
from streamll.dspy_callback import StreamllDSPyCallback
from streamll.sinks import TerminalSink

# Try to import RedisSink, fallback to None if not available
RedisSink = None
try:
    from streamll.sinks import RedisSink  # noqa: F401
except ImportError:
    pass

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class StreamllRetriever(dspy.Module):
    """Custom DSPy retriever using pgvector."""

    def __init__(self, index: VectorStoreIndex, top_k: int = 3):
        super().__init__()
        self.index = index
        self.top_k = top_k
        self.name = "StreamllDocRetriever"
        self.description = (
            f"Retrieves StreamLL documentation using pgvector similarity search (top_k={top_k})"
        )

    def forward(self, query: str) -> list[str]:
        """Retrieve relevant documents for query."""
        retriever = self.index.as_retriever(similarity_top_k=self.top_k)
        nodes = retriever.retrieve(query)

        # Format retrieved content
        passages = []
        for i, node in enumerate(nodes, 1):
            title = Path(node.metadata.get("file_name", "document")).stem
            content = node.text.strip()
            passage = f"[Document {i}: {title}]\n{content}"
            passages.append(passage)

        return passages


# Demo-specific helper functions removed - now using StreamLL core streaming!


class StreamllRAG(dspy.Module):
    """RAG pipeline with StreamLL monitoring."""

    def __init__(self, retriever: StreamllRetriever):
        super().__init__()
        self.retriever = retriever

        # DSPy signature for RAG
        self.generate = dspy.ChainOfThought("context, question -> answer")

        # Use StreamLL core streaming functionality
        self.streaming_generate = streamll.create_streaming_wrapper(
            self.generate, signature_field_name="answer", operation="answer_generation"
        )

    def forward(self, question: str):
        """Process RAG query with full StreamLL monitoring."""

        # Step 1: Retrieve relevant documents (monitored automatically by DSPy tool callback)
        streamll.emit("start", operation="document_retrieval", data={"query": question[:100]})
        passages = self.retriever(question)
        context = "\n\n".join(passages)
        streamll.emit(
            "end",
            operation="document_retrieval",
            data={"passages_count": len(passages), "context_length": len(context)},
        )

        # Step 2: Generate answer using LLM with token streaming (monitored automatically by DSPy LM callback)
        streamll.emit("start", operation="answer_generation", data={"context_length": len(context)})
        prediction = self.streaming_generate(context=context, question=question)
        streamll.emit("end", operation="answer_generation")

        # Step 3: Format response with sources
        response = {
            "answer": prediction.answer,
            "sources": len(passages),
            "context_length": len(context),
            "reasoning": getattr(prediction, "rationale", None),
        }

        return response


def setup_streamll():
    """Configure StreamLL with both terminal and Redis sinks."""

    sinks = [
        # Beautiful terminal output for development
        TerminalSink()
    ]

    # Add Redis sink if Redis is available
    if RedisSink is not None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            redis_sink = RedisSink(
                url=redis_url,
                stream_key="streamll_rag_demo",
                circuit_breaker=True,
                failure_threshold=3,
                recovery_timeout=10.0,
            )
            sinks.append(redis_sink)
        except Exception as e:
            logger.warning(f"Redis sink not available: {e}")

    # Configure streamll globally
    streamll.configure(sinks=sinks)

    return sinks


def setup_dspy():
    """Configure DSPy with Gemini and StreamLL callback."""

    # Configure Gemini LLM
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        sys.exit(1)

    lm = dspy.LM(
        model="gemini/gemini-2.5-flash",
        api_key=gemini_api_key,
        # Using DSPy's default max_tokens=4000
    )

    # Configure DSPy with StreamLL callback
    dspy.configure(
        lm=lm, callbacks=[StreamllDSPyCallback(include_inputs=True, include_outputs=True)]
    )



def setup_vector_store():
    """Setup vector store connection."""

    # Configure LlamaIndex
    Settings.embed_model = GoogleGenAIEmbedding(
        model_name="gemini-embedding-001", api_key=os.getenv("GEMINI_API_KEY")
    )

    # Connect to existing pgvector store
    vector_store = PGVectorStore.from_params(
        database=os.getenv("DATABASE_NAME", "streamll_rag"),
        host=os.getenv("DATABASE_HOST", "localhost"),
        password=os.getenv("DATABASE_PASSWORD", "streamll_demo"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        user=os.getenv("DATABASE_USER", "streamll"),
        table_name="documents",
        embed_dim=3072,
    )

    # Create index from existing vector store
    index = VectorStoreIndex.from_vector_store(vector_store)

    return index


def demo_queries():
    """Return demo queries to showcase the RAG system."""
    return [
        "How does StreamLL integrate with DSPy applications?",
        "What production resilience features does StreamLL provide?",
        "Explain the circuit breaker pattern in StreamLL's Redis sink",
        "How can I monitor LLM token usage with StreamLL?",
        "What makes StreamLL suitable for enterprise deployments?",
    ]


def interactive_demo(rag_pipeline: StreamllRAG):
    """Run interactive demo with sample queries."""

    while True:
        try:
            query = input("💬 Ask about StreamLL: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                break
            elif query.lower() == "demo":
                for _i, sample_query in enumerate(demo_queries(), 1):
                    process_query(rag_pipeline, sample_query)
                continue
            elif not query:
                continue

            process_query(rag_pipeline, query)

        except KeyboardInterrupt:
            break
        except EOFError:
            # Non-interactive mode - run demo queries and exit
            for _i, sample_query in enumerate(demo_queries(), 1):
                process_query(rag_pipeline, sample_query)
            break
        except Exception:
            break  # Exit on other errors to prevent infinite loops



def process_query(rag_pipeline: StreamllRAG, query: str):
    """Process a single query with StreamLL monitoring."""

    # Execute RAG pipeline (fully monitored by StreamLL)
    streamll.emit("start", operation="rag_query", data={"query": query[:100]})
    response = rag_pipeline(query)
    streamll.emit(
        "end", operation="rag_query", data={"answer_length": len(str(response["answer"]))}
    )

    # Display results
    if response["reasoning"]:
        pass


def main():
    """Main demo application."""

    # Check requirements
    required_env = ["GEMINI_API_KEY"]
    missing_env = [var for var in required_env if not os.getenv(var)]

    if missing_env:
        sys.exit(1)

    try:
        # Setup components
        sinks = setup_streamll()
        setup_dspy()
        index = setup_vector_store()

        # Create RAG pipeline
        retriever = StreamllRetriever(index, top_k=3)
        rag_pipeline = StreamllRAG(retriever)


        # Show monitoring setup
        for sink in sinks:
            type(sink).__name__
            if hasattr(sink, "stream_key"):
                pass
            else:
                pass

        # Run interactive demo
        interactive_demo(rag_pipeline)

    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        # Cleanup
        try:
            # Stop all sinks gracefully
            for sink in sinks:
                if hasattr(sink, "stop") and sink.is_running:
                    sink.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
