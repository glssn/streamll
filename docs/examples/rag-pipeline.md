# RAG Pipeline Monitoring

Learn how to monitor Retrieval-Augmented Generation (RAG) pipelines with StreamLL.

## Complete RAG Example

This example shows a full RAG pipeline with document retrieval and answer generation:

```python
import streamll
import dspy
from streamll.sinks import TerminalSink, RedisSink

@streamll.instrument(sinks=[
    TerminalSink(),  # Beautiful development output
    RedisSink("redis://localhost:6379", stream_key="rag_events")  # Production monitoring
])
class RAGPipeline(dspy.Module):
    """RAG pipeline with StreamLL monitoring."""
    
    def __init__(self, retriever, top_k=3):
        super().__init__()
        self.retriever = retriever
        self.top_k = top_k
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        # Step 1: Retrieve relevant documents
        docs = self.retriever(question, k=self.top_k)
        context = "\n\n".join([doc.text for doc in docs])
        
        # Step 2: Generate answer from context
        result = self.generate(context=context, question=question)
        
        return {
            "answer": result.answer,
            "reasoning": result.reasoning,
            "source_docs": len(docs),
            "context_length": len(context)
        }

# Configure DSPy
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash"))

# Create retriever (using DSPy's built-in retriever)
retriever = dspy.Retrieve(k=3)

# Create and use RAG pipeline
rag = RAGPipeline(retriever)
result = rag("What are the benefits of renewable energy?")
```

**StreamLL Output:**
```bash
[16:52:13.123] ▶ module_forward [RAGPipeline] (a1b2c3d4)
  {
    "args": ["What are the benefits of renewable energy?"],
    "kwargs": {}
  }
[16:52:13.125] ▶ retrieve_call (e5f6g7h8)
  {
    "query": "What are the benefits of renewable energy?",
    "k": 3
  }
[16:52:13.856] ■ retrieve_call (e5f6g7h8)
  {
    "documents_found": 3,
    "total_chars": 2847
  }
[16:52:13.857] ▶ llm_call (i9j0k1l2)
[16:52:16.234] ■ llm_call (i9j0k1l2)
[16:52:16.235] ■ module_forward [RAGPipeline] (a1b2c3d4)
  {
    "outputs": {
      "answer": "Renewable energy offers numerous benefits...",
      "source_docs": 3,
      "context_length": 2847
    }
  }
```

## Advanced RAG with Custom Retrieval

Monitor custom retrieval systems (like vector databases):

```python
import streamll
import dspy

class VectorRetriever(dspy.Module):
    """Custom vector database retriever."""
    
    def __init__(self, vector_db):
        super().__init__()
        self.vector_db = vector_db
    
    def forward(self, query, k=3):
        # Custom retrieval logic
        embeddings = self.vector_db.embed(query)
        docs = self.vector_db.search(embeddings, k=k)
        return docs

@streamll.instrument
class AdvancedRAG(dspy.Module):
    """RAG with custom vector retrieval."""
    
    def __init__(self, vector_db):
        super().__init__()
        self.retriever = VectorRetriever(vector_db)
        self.rerank = dspy.Predict("query, documents -> ranked_documents")
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        # Step 1: Vector retrieval
        docs = self.retriever(question, k=10)
        
        # Step 2: Rerank documents  
        ranked = self.rerank(query=question, documents=docs)
        
        # Step 3: Generate answer
        context = "\n".join(ranked.ranked_documents[:3])
        result = self.generate(context=context, question=question)
        
        return result
```

## Token Streaming for RAG

Enable real-time token streaming to see answers build up word-by-word:

```python
import streamll

# Create RAG pipeline
rag = RAGPipeline(retriever)

# Wrap with streaming
streaming_rag = streamll.create_streaming_wrapper(
    rag,
    signature_field_name="answer"  # Stream the "answer" field
)

# Watch tokens arrive in real-time
result = streaming_rag("Explain quantum computing in simple terms")
```

**Streaming Output:**
```bash
[16:53:45.123] ▶ module_forward [RAGPipeline] (m3n4o5p6)
[16:53:45.124] ▶ retrieve_call (q7r8s9t0)
[16:53:45.567] ■ retrieve_call (q7r8s9t0)
[16:53:45.568] ▶ answer_generation (m3n4o5p6)
[16:53:45.789] • answer_generation (m3n4o5p6) 'Quantum'
[16:53:45.823] • answer_generation (m3n4o5p6) ' computing'
[16:53:45.867] • answer_generation (m3n4o5p6) ' is'
[16:53:45.901] • answer_generation (m3n4o5p6) ' a'
[16:53:45.934] • answer_generation (m3n4o5p6) ' revolutionary'
# ... more tokens stream in real-time
[16:53:49.123] ■ answer_generation (m3n4o5p6)
```

## Production RAG Monitoring

Real-world RAG pipeline with comprehensive monitoring:

```python
import streamll
from streamll.sinks import RedisSink
import dspy

@streamll.instrument(sinks=[
    RedisSink(
        "redis://prod-redis:6379",
        stream_key="rag_production",
        buffer_size=10000,  # Buffer events during outages
        circuit_breaker=True  # Prevent cascade failures
    )
])
class ProductionRAG(dspy.Module):
    """Production RAG with resilience monitoring."""
    
    def __init__(self, vector_store, llm_model="gemini/gemini-2.0-flash"):
        super().__init__()
        self.retriever = VectorRetriever(vector_store)
        self.generate = dspy.ChainOfThought("context, question -> answer")
        
    def forward(self, question):
        try:
            # Monitored retrieval
            docs = self.retriever(question, k=5)
            
            if not docs:
                raise ValueError("No relevant documents found")
                
            # Prepare context
            context = self._prepare_context(docs)
            
            # Monitored generation
            result = self.generate(context=context, question=question)
            
            # Return structured response
            return {
                "answer": result.answer,
                "confidence": self._calculate_confidence(result),
                "sources": len(docs),
                "context_used": len(context)
            }
            
        except Exception as e:
            # StreamLL automatically captures errors
            raise
    
    def _prepare_context(self, docs):
        # Custom context preparation
        return "\n\n".join([
            f"Source {i+1}: {doc.text}" 
            for i, doc in enumerate(docs[:3])
        ])
    
    def _calculate_confidence(self, result):
        # Custom confidence scoring
        return 0.85  # Placeholder
```

## Multi-Stage RAG Pipeline

Monitor complex RAG with multiple processing stages:

```python
@streamll.instrument
class MultiStageRAG(dspy.Module):
    """RAG with query preprocessing and answer postprocessing."""
    
    def __init__(self, vector_store):
        super().__init__()
        self.query_preprocessor = dspy.Predict("raw_query -> processed_query")
        self.retriever = VectorRetriever(vector_store)
        self.answer_generator = dspy.ChainOfThought("context, question -> answer")
        self.answer_postprocessor = dspy.Predict("raw_answer -> final_answer")
    
    def forward(self, raw_query):
        # Stage 1: Preprocess query
        processed = self.query_preprocessor(raw_query=raw_query)
        
        # Stage 2: Retrieve documents
        docs = self.retriever(processed.processed_query, k=5)
        
        # Stage 3: Generate initial answer
        context = "\n".join([doc.text for doc in docs])
        raw_answer = self.answer_generator(
            context=context, 
            question=processed.processed_query
        )
        
        # Stage 4: Postprocess answer
        final = self.answer_postprocessor(raw_answer=raw_answer.answer)
        
        return {
            "original_query": raw_query,
            "processed_query": processed.processed_query,
            "answer": final.final_answer,
            "reasoning": raw_answer.reasoning,
            "sources": len(docs)
        }
```

**Multi-stage monitoring:**
```bash
[16:55:12.123] ▶ module_forward [MultiStageRAG] (u1v2w3x4)
[16:55:12.124] ▶ llm_call (y5z6a7b8) # query preprocessing
[16:55:12.567] ■ llm_call (y5z6a7b8)
[16:55:12.568] ▶ retrieve_call (c9d0e1f2) # retrieval
[16:55:13.123] ■ retrieve_call (c9d0e1f2)
[16:55:13.124] ▶ llm_call (g3h4i5j6) # answer generation
[16:55:15.789] ■ llm_call (g3h4i5j6)
[16:55:15.790] ▶ llm_call (k7l8m9n0) # answer postprocessing
[16:55:16.234] ■ llm_call (k7l8m9n0)
[16:55:16.235] ■ module_forward [MultiStageRAG] (u1v2w3x4)
```

## RAG Analytics with Redis

Analyze RAG performance using Redis events:

```python
import redis
import json
from collections import defaultdict

def analyze_rag_performance():
    """Analyze RAG pipeline performance from Redis events."""
    
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Read all RAG events
    entries = r.xread({"rag_events": "0"})
    
    stats = defaultdict(list)
    
    for stream_name, stream_entries in entries:
        for entry_id, fields in stream_entries:
            event = json.loads(fields["event"])
            
            if event["event_type"] == "module_forward":
                if "execution_time_ms" in event.get("data", {}):
                    stats["execution_times"].append(event["data"]["execution_time_ms"])
            
            elif event["event_type"] == "retrieve_call":
                if "documents_found" in event.get("data", {}):
                    stats["doc_counts"].append(event["data"]["documents_found"])
    
    # Calculate metrics
    avg_time = sum(stats["execution_times"]) / len(stats["execution_times"])
    avg_docs = sum(stats["doc_counts"]) / len(stats["doc_counts"])
    
    print(f"Average execution time: {avg_time:.2f}ms")
    print(f"Average documents retrieved: {avg_docs:.1f}")
    
    return stats

# Run analytics
analyze_rag_performance()
```

## Best Practices for RAG Monitoring

### 1. Monitor Each Stage
Use separate monitoring for retrieval, ranking, and generation.

### 2. Track Document Quality
Monitor number of documents retrieved and context length.

### 3. Watch for Empty Retrievals
Alert when no relevant documents are found.

### 4. Monitor Token Streaming
Use streaming for user-facing applications to show progress.

### 5. Production Resilience
Use Redis sink with circuit breaker for production deployments.

### 6. Performance Analytics
Regularly analyze execution times and retrieval effectiveness.

## Next Steps

- **[Token Streaming Guide](streaming.md)** - Real-time response monitoring
- **[Production Deployment](../production/redis-sink.md)** - Scale your RAG monitoring
- **[Custom Events](custom-events.md)** - Add domain-specific monitoring