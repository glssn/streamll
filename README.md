# StreamLL

**Real-time observability for DSPy applications**

[![Tests](https://github.com/streamll/streamll/workflows/tests/badge.svg)](https://github.com/streamll/streamll/actions)
[![Coverage](https://codecov.io/gh/streamll/streamll/branch/main/graph/badge.svg)](https://codecov.io/gh/streamll/streamll)
[![PyPI](https://img.shields.io/pypi/v/streamll.svg)](https://pypi.org/project/streamll/)
[![Python](https://img.shields.io/pypi/pyversions/streamll.svg)](https://pypi.org/project/streamll/)

> **The Problem**: You've built an amazing DSPy application, but in production it's a black box. When it fails, you have no idea why. When it's slow, you can't see where time is spent. When tokens stream, you can't monitor them in real-time.

> **The Solution**: StreamLL provides production-grade observability for DSPy applications with a single decorator. Monitor every LLM call, tool usage, and streaming token in real-time.

## ⚡ Quick Demo

```python
import streamll
import dspy

# Add one decorator - get full observability
@streamll.instrument
class RAGPipeline(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve(k=3)
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        docs = self.retrieve(question)
        return self.generate(context=docs, question=question)

# Configure your LLM
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash"))

# Run your pipeline - see everything in real-time
pipeline = RAGPipeline()
result = pipeline("What is machine learning?")
```

**Output**: Real-time terminal dashboard showing:
```bash
[16:31:42.156] ▶ document_retrieval (a1b2c3d4)
  {"query": "What is machine learning?", "top_k": 3}
[16:31:42.891] ■ document_retrieval (a1b2c3d4) 
  {"passages_count": 3, "context_length": 2847}
[16:31:42.920] ▶ answer_generation (a1b2c3d4)
[16:31:43.156] • answer_generation (a1b2c3d4) 'Machine learning'
[16:31:43.298] • answer_generation (a1b2c3d4) ' is a subset'
[16:31:43.445] • answer_generation (a1b2c3d4) ' of artificial intelligence...'
[16:31:46.782] ■ answer_generation (a1b2c3d4)
  {"total_tokens": 287, "cost": "$0.0023"}
```

## 🚀 Installation & Quick Start

### 1. Install StreamLL

```bash
# Basic installation (requires DSPy 2.6.24+)
pip install streamll

# With Redis sink for production
pip install streamll[redis]

# All optional dependencies
pip install streamll[all]
```

**Requirements**: Python 3.11+ and DSPy 2.6.24+ (streaming and callback features)

### 2. Add the decorator

```python
import streamll

@streamll.instrument  # ← Add this line
class YourDSPyModule(dspy.Module):
    # Your existing code unchanged
    pass
```

### 3. See your application in action

That's it! StreamLL automatically captures:
- 🎯 **LLM calls**: Prompts, completions, token usage, costs
- 🔧 **Tool usage**: Retrievers, APIs, custom tools  
- 🌊 **Streaming tokens**: Real-time token-by-token responses
- ⚡ **Performance**: Execution time, success/failure rates
- 🚨 **Errors**: LLM failures, API timeouts, rate limits

## ✨ Key Features

### 🎯 **Multiple Streaming Backends**
Choose the right backend for your architecture:

| Backend | Use Case | Performance | Setup |
|---------|----------|-------------|-------|
| **TerminalSink** | Development, debugging | <1ms latency | Zero setup |
| **RedisSink** | Real-time dashboards | 100K events/sec | Minimal setup |
| **RabbitMQSink** | Enterprise, compliance | Durable queuing | Moderate setup |

### 🎨 **Beautiful Development Experience**
Real-time colored output perfect for debugging:

```python
from streamll.sinks import TerminalSink

streamll.configure(sinks=[TerminalSink()])
# Get instant visual feedback while coding!
```

### 🚀 **Production-Ready Redis Streaming**
High-performance streaming for real-time dashboards:

```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="ai_events",
    circuit_breaker=True  # Production-grade resilience
)

streamll.configure(sinks=[redis_sink])
# Events stream to Redis → dashboards, analytics, monitoring
```

### 🏢 **Enterprise RabbitMQ Integration**
Durable message queuing for compliance and workflows:

```python
from streamll.sinks import RabbitMQSink

rabbitmq_sink = RabbitMQSink(
    amqp_url="amqp://localhost:5672/",
    exchange="ai_events", 
    routing_key="ai.{operation}.{event_type}",
    durable=True  # Survive server restarts
)

streamll.configure(sinks=[rabbitmq_sink])
# Events route to: audit, alerts, compliance, workflows
```

### 🌊 **Real-Time Token Streaming**
Monitor streaming LLM responses token-by-token:

```python
import streamll

# Enable token streaming
streaming_module = streamll.create_streaming_wrapper(
    my_module, 
    signature_field_name="answer"
)

# See tokens arrive in real-time
result = streaming_module(question="Explain quantum computing")
```

### 🏢 **Enterprise-Grade Architecture**
- **Zero external dependencies** - runs entirely on your infrastructure
- **Multi-sink routing** - send events to multiple destinations
- **Instance isolation** - no global state conflicts
- **Memory efficient** - minimal overhead on your applications

## 📊 Production Monitoring

StreamLL is designed for production LLM applications. Stream events to your existing infrastructure:

| Sink | Use Case | Features |
|------|----------|----------|
| **TerminalSink** | Development, debugging | Colored output, real-time display |
| **RedisSink** | Production, analytics | Circuit breaker, buffering, scaling |  
| **FileSink** | Logging, compliance | Structured JSON, rotation |
| **Custom Sinks** | Your infrastructure | Implement `BaseSink` interface |

## 🎯 Real-World Example

See StreamLL monitoring a complete RAG pipeline with pgvector and token streaming:

```bash
git clone https://github.com/streamll/streamll
cd streamll/demos/streamll-rag-local
docker-compose up -d  # Start Redis + pgvector
uv run python src/rag.py
```

**Features demonstrated**:
- Document retrieval from pgvector
- Real-time token streaming from Gemini
- Production Redis event storage
- Circuit breaker resilience patterns

## 📚 Documentation

- **[Quick Start Guide](docs/quickstart.md)** - Get running in 5 minutes
- **[Production Deployment](docs/production/)** - Redis, monitoring, scaling
- **[Examples](docs/examples/)** - RAG, agents, custom tools
- **[API Reference](docs/api/)** - Complete decorator and streaming API

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙋‍♀️ Support

- **GitHub Issues**: Bug reports and feature requests
- **Discussions**: Questions and community support
- **Documentation**: Comprehensive guides and examples

---

**Built for the DSPy ecosystem** 🚀

StreamLL is specifically designed for DSPy applications. It understands your modules, signatures, and workflows natively, providing observability that just works out of the box.