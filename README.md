# streamll

Production-ready streaming for DSPy applications.

Stream every step of your AI application - like retrieval, reasoning and token generation — directly into Redis, RabbitMQ, and your existing event infrastructure.

## Quick Start

```bash
# Using uv (recommended)
uv add streamll

# Or using pip
pip install streamll
```

[![asciicast](https://asciinema.org/a/Lu7QCpvNtrShpYuq9riDx2CTr.svg)](https://asciinema.org/a/Lu7QCpvNtrShpYuq9riDx2CTr)

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

qa = QA()
result = qa("Explain quantum computing")
```

### Class-based Signatures

```python
class Analysis(dspy.Signature):
    """Analyze text sentiment."""
    text: str = dspy.InputField()
    analysis: str = dspy.OutputField()

@streamll.instrument(stream_fields=["analysis"])
class Analyzer(dspy.Module):
    def __init__(self):
        self.analyze = dspy.Predict(Analysis)

    def forward(self, text):
        return self.analyze(text=text)
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

*NATS and Kafka support coming soon.*

## Custom Events

```python
@streamll.instrument
class RAGPipeline(dspy.Module):
    def forward(self, question):
        with streamll.trace("retrieval") as ctx:
            docs = self.retrieve(question)
            ctx.emit("docs_found", count=len(docs))

        answer = self.generate(docs=docs, question=question)
        return answer
```

## Features

- **Token streaming** - Real-time LLM output
- **Auto buffering** - Never lose events
- **Circuit breakers** - Graceful degradation
- **Zero overhead** - Async, non-blocking

## Installation

```bash
# Basic (terminal output only)
uv add streamll

# With Redis for production
uv add "streamll[redis]"

# With RabbitMQ  
uv add "streamll[rabbitmq]"

# Everything
uv add "streamll[all]"
```

## Development

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src/streamll
```

## License

Apache 2.0
