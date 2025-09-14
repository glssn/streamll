# streamll

Production-ready streaming for DSPy applications.

Stream every step of your AI application - like retrieval, reasoning and token generation - directly into Redis, RabbitMQ, and your existing event infrastructure.

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

## Quick start

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

## Production use

Send events to Redis or RabbitMQ instead of the terminal:

```python
from streamll.sinks import RedisSink

sink = RedisSink(redis_url="redis://localhost:6379", stream_key="ml_events")

@streamll.instrument(sinks=[sink], stream_fields=["answer"])
class QA(dspy.Module):
    def __init__(self):
        self.generate = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        return self.generate(question=question)
```

Consume events in another service:

```python
from streamll import EventConsumer

consumer = EventConsumer("redis://localhost:6379", target="ml_events")

@consumer.on("token")
async def handle_token(event):
    print(event.data["token"], end="", flush=True)

await consumer.run()
```

## Custom events

Emit custom events within your processing:

```python
@streamll.instrument
class RAGPipeline(dspy.Module):
    def forward(self, question):
        with streamll.trace("retrieval") as ctx:
            docs = self.retrieve(question)
            ctx.emit("docs_found", data={"count": len(docs)})

        answer = self.generate(docs=docs, question=question)
        return answer
```

## Event correlation

Attach correlation IDs that persist across all events:

```python
# In your API handler
streamll.set_context(
    conversation_id="conv_123",
    request_id="req_456"
)

# All subsequent events include this context
qa = QA()
result = qa("What is quantum computing?")

# Consumer can filter by context
@consumer.on("token")
async def handle_token(event):
    if event.data.get("conversation_id") == "conv_123":
        # Handle this specific conversation
        pass
```

## Development

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=src/streamll

# Start test services (Redis, RabbitMQ)
docker-compose -f tests/docker-compose.yml up -d
```

## License

Apache 2.0