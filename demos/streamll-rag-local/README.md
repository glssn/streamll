# StreamLL Real-World RAG Demo

This demo showcases **StreamLL** monitoring a production-grade RAG (Retrieval-Augmented Generation) pipeline running entirely on local infrastructure.

## 🎯 What This Demo Shows

- **DSPy Integration**: Complete LLM orchestration with automatic monitoring
- **Real-Time Monitoring**: Watch every LLM call, token usage, and tool invocation
- **Production Resilience**: Circuit breaker patterns for Redis connectivity  
- **Local Infrastructure**: pgvector + Redis running in Docker
- **Multi-Sink Architecture**: Terminal output + Redis streaming simultaneously

## 🏗️ Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Query     │────│ DSPy RAG     │────│ StreamLL    │
│   Input     │    │ Pipeline     │    │ Monitoring  │
└─────────────┘    └──────────────┘    └─────────────┘
                          │                    │
                   ┌──────┴──────┐       ┌─────┴─────┐
                   │             │       │           │
              ┌────▼───┐    ┌────▼────┐  ▼           ▼
              │pgvector│    │ Gemini  │ TerminalSink RedisSink
              │Retrieval│    │ LLM     │ (Beautiful)  (Streaming)
              └────────┘    └─────────┘
```

## 🚀 Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.9+
- OpenAI API key (for embeddings)
- Gemini API key (for LLM)

### 2. Environment Setup

```bash
# Clone and navigate to demo
cd demos/streamll-rag-local/

# Copy environment template
cp .env.example .env

# Edit .env with your API keys:
# OPENAI_API_KEY=your_openai_key
# GEMINI_API_KEY=your_gemini_key
```

### 3. Start Infrastructure

```bash
# Start pgvector + Redis with Docker
docker-compose up -d

# Wait for services to be ready
docker-compose logs -f postgres  # Wait for "ready to accept connections"
```

### 4. Install Dependencies

```bash
# Install demo dependencies with uv (recommended)
uv pip install -e ../..  # Install streamll from parent directory
uv pip install -e .      # Install demo dependencies

# Or with traditional pip:
pip install -e ../..
pip install -e .
```

### 5. Index Documents

```bash
# Load StreamLL docs into pgvector
uv run python src/index.py
```

Expected output:
```
🚀 Starting document indexing pipeline
✅ LlamaIndex configured with OpenAI embeddings
✅ Connected to pgvector database
✅ Loaded 3 documents from .../data
📊 Creating embeddings and storing in pgvector...
✅ Documents successfully indexed in pgvector!
```

### 6. Run RAG Demo

```bash
# Test the demo non-interactively first
uv run python test_rag.py

# Or run interactive RAG demo
uv run python src/rag.py
```

## 🎮 Using the Demo

### Interactive Mode

```
🎯 StreamLL RAG Demo - Interactive Mode
💬 Ask about StreamLL: How does StreamLL integrate with DSPy?
```

### Sample Queries

Type `demo` to run curated sample queries:
- How does StreamLL integrate with DSPy applications?
- What production resilience features does StreamLL provide?
- Explain the circuit breaker pattern in StreamLL's Redis sink

### StreamLL Monitoring in Action

Watch StreamLL capture everything in real-time:

**Terminal Output** (TerminalSink):
```
▶ [12:34:56] LM Call: gemini/gemini-2.5-flash
  📝 Prompt: You are given context and a question. Answer based on the context...
  💬 Response: StreamLL integrates with DSPy through callback mechanisms...
  📊 Tokens: 156 input, 89 output (245 total)

• [12:34:56] Tool: StreamllDocRetriever  
  🔍 Query: How does StreamLL integrate with DSPy?
  📄 Retrieved: 3 documents (2,847 chars)
```

**Redis Streams** (Production monitoring):
```bash
# View events in Redis
redis-cli XREAD STREAMS streamll_rag_demo 0
```

## 🔧 Configuration Options

### StreamLL Sinks

```python
# Configure different monitoring outputs
streamll.configure([
    TerminalSink(),                    # Development debugging
    RedisSink(                        # Production streaming
        url="redis://localhost:6379",
        stream_key="ml_events",
        circuit_breaker=True          # Resilience patterns
    )
])
```

### Privacy Controls

```python
# Control sensitive data capture
dspy.configure(
    lm=lm,
    callback=streamll.dspy_callback(
        include_inputs=False,   # Exclude prompt data
        include_outputs=False   # Exclude LLM responses
    )
)
```

## 📊 What Gets Monitored

### LLM Calls (DSPy LM Callback)
- Model provider and version
- Complete prompts with template substitutions
- Full LLM responses and reasoning
- Token usage (input/output/total)
- Response latency and errors
- Streaming token delivery

### Tool Usage (DSPy Tool Callback)  
- Tool identification and descriptions
- Input arguments and parameters
- Tool results and retrieved content
- Execution performance
- Error handling and timeouts

### Execution Context
- Unique execution IDs for request tracing
- Operation hierarchy (retrieval → generation)
- End-to-end query processing time
- Circuit breaker state and recovery

## 🏢 Production Deployment

This demo architecture scales to production:

### Infrastructure Independence
- **No SaaS dependencies**: Everything runs on your infrastructure
- **Data sovereignty**: Documents and events never leave your environment
- **Cost effectiveness**: No per-event pricing or external fees

### Horizontal Scaling
```python
# Multiple Redis consumer groups
RedisSink(
    url="redis://redis-cluster:6379",
    stream_key="production_events",
    consumer_group="rag_processors",
    consumer_name="worker_1"
)

# Load balancing across instances
streamll.configure_module(rag_instance_1, [redis_sink_1])
streamll.configure_module(rag_instance_2, [redis_sink_2])
```

### Production Resilience
```python
# Circuit breaker configuration
RedisSink(
    circuit_breaker=True,
    failure_threshold=3,      # Open after 3 failures  
    recovery_timeout=30.0,    # Retry every 30 seconds
    buffer_size=10000         # Buffer during outages
)
```

## 🔍 Monitoring & Debugging

### Real-Time Event Streams

```bash
# Monitor Redis events live
redis-cli --latency-history XREAD STREAMS streamll_rag_demo $

# Query specific executions
redis-cli XREAD STREAMS streamll_rag_demo 0 | grep execution_id:abc123

# Analyze token usage patterns  
redis-cli XREAD STREAMS streamll_rag_demo 0 | grep token_usage
```

### Performance Analysis

```python
# Custom sink for metrics
class MetricsSink(BaseSink):
    def handle_event(self, event):
        if event.event_type == "end" and event.operation == "lm_call":
            # Track response times
            latency = event.data.get("duration_ms", 0)
            self.metrics.record_latency(latency)
            
            # Track token costs
            tokens = event.data.get("token_usage", {})
            self.metrics.record_cost(tokens)
```

## 🧹 Cleanup

```bash
# Stop demo
Ctrl+C

# Stop infrastructure
docker-compose down

# Remove volumes (optional)
docker-compose down -v
```

## 🛠️ Troubleshooting

### pgvector Connection Issues
```bash
# Check PostgreSQL logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U streamll -d streamll_rag -c "SELECT COUNT(*) FROM documents;"
```

### Redis Connection Issues
```bash
# Check Redis connectivity
redis-cli ping

# View Redis logs
docker-compose logs redis

# Check circuit breaker status
python -c "import redis; r=redis.Redis(); print(r.ping())"
```

### API Key Issues
```bash
# Verify environment variables
source .env && echo $OPENAI_API_KEY | head -c 20
source .env && echo $GEMINI_API_KEY | head -c 20

# Test OpenAI embeddings
python -c "
import openai
import os
client = openai.OpenAI()
response = client.embeddings.create(model='text-embedding-ada-002', input='test')
print(f'Embedding dimension: {len(response.data[0].embedding)}')"
```

## 📈 Next Steps

### Extend the Demo
- Add more document types (PDF, JSON, CSV)
- Implement query refinement with StreamLL tracking
- Add conversation memory with Redis persistence
- Create Grafana dashboards from Redis streams

### Production Features
- Add authentication and authorization
- Implement rate limiting and quotas
- Set up alerting on circuit breaker events
- Create audit trails for compliance

### Multi-Model Support
- OpenAI GPT-4 for reasoning
- Anthropic Claude for analysis  
- Local models via Ollama
- All monitored by StreamLL automatically

---

**🎉 StreamLL demonstrates that production LLM observability doesn't require external SaaS platforms. Everything runs on your infrastructure, giving you complete control over your data and costs.**