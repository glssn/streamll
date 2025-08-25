# StreamLL

Real-time observability for DSPy applications with token streaming, Redis, and RabbitMQ.

## Quick Start

```bash
pip install streamll
```

```python
import dspy
import streamll

# Stream tokens to terminal
@streamll.instrument(stream_fields=["answer"])
class QA(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought("question -> answer")
    
    def forward(self, question):
        return self.generate(question=question)

# Configure DSPy  
dspy.configure(lm=dspy.LM("openai/gpt-4o-mini"))

# Run - tokens stream in real-time
qa = QA()
result = qa("Explain quantum computing")
```

## Production Sinks

### Redis Streams
```python
sink = streamll.RedisSink(url="redis://localhost:6379")
streamll.configure(sinks=[sink])
```

### RabbitMQ
```python
sink = streamll.RabbitMQSink(url="amqp://localhost:5672")
streamll.configure(sinks=[sink])
```

## Automatic Tracing

```python
with streamll.trace("rag_pipeline") as t:
    # Auto-emits START event
    result = rag.forward(question)
    # Auto-emits END event (or ERROR if exception)
    
# Emit custom events
t.emit("retrieval_complete", doc_count=3)
```

## Features

- **Token streaming** - Real-time LLM output
- **Auto buffering** - Never lose events  
- **Circuit breakers** - Graceful degradation
- **Batched writes** - 82x performance boost
- **Zero overhead** - Async, non-blocking

## Install Options

```bash
pip install streamll[redis]     # With Redis
pip install streamll[rabbitmq]  # With RabbitMQ  
pip install streamll[all]       # Everything
```

MIT License