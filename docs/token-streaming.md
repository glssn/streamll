# Token Streaming Guide

StreamLL provides real-time token streaming for DSPy modules, allowing you to see LLM responses as they're generated rather than waiting for completion.

## Quick Start

```python
import streamll
import dspy

@streamll.instrument(stream_fields=['answer'])  # Enable token streaming
class SimpleQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        return self.predict(question=question)

# Tokens will stream to terminal as they're generated
qa = SimpleQA()
result = qa("What is machine learning?")
```

## How It Works

StreamLL intercepts DSPy's prediction modules and uses the LLM's streaming API to emit token events as they arrive. Each token is emitted as a `TokenEvent` with:

- `token`: The text chunk
- `token_index`: Sequential position in the stream
- `field`: Which output field this token belongs to
- `finish_reason`: Why streaming stopped (if applicable)

## Supported Modules

### dspy.Predict

For simple predictions, specify the output field name:

```python
@streamll.instrument(stream_fields=['answer'])
class QA(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict("question -> answer")
```

### dspy.ChainOfThought

ChainOfThought has two output fields: `reasoning` and `answer`. You can stream either or both:

```python
# Stream both reasoning and answer
@streamll.instrument(stream_fields=['reasoning', 'answer'])
class ReasoningQA(dspy.Module):
    def __init__(self):
        self.cot = dspy.ChainOfThought("question -> answer")

# Stream only the final answer
@streamll.instrument(stream_fields=['answer'])
class ReasoningQA(dspy.Module):
    def __init__(self):
        self.cot = dspy.ChainOfThought("question -> answer")
```

### Multiple Predictors

Stream different fields from different predictors:

```python
@streamll.instrument(stream_fields=['summary', 'answer'])
class ComplexPipeline(dspy.Module):
    def __init__(self):
        self.summarize = dspy.Predict("text -> summary")
        self.answer = dspy.Predict("context, question -> answer")
    
    def forward(self, text, question):
        summary = self.summarize(text=text)
        answer = self.answer(context=summary.summary, question=question)
        return answer
```

## Field Discovery

### Automatic Field Detection

ChainOfThought automatically has `reasoning` and `answer` fields:

```python
# ChainOfThought signature: "question -> answer"
# Actual fields: question -> reasoning, answer

cot = dspy.ChainOfThought("question -> answer")
# Output fields: reasoning, answer
```

### Finding Available Fields

To discover what fields are available for streaming:

```python
# For Predict
predict = dspy.Predict("question -> answer")
print(predict.signature.output_fields)
# Output: {'answer': FieldInfo(...)}

# For ChainOfThought
cot = dspy.ChainOfThought("question -> answer")
print(cot.predict.signature.output_fields)  # Note: .predict attribute
# Output: {'reasoning': FieldInfo(...), 'answer': FieldInfo(...)}
```

### Custom Signatures

With custom signatures, use your defined field names:

```python
class CustomSignature(dspy.Signature):
    """Custom task with specific fields."""
    query = dspy.InputField(desc="The search query")
    analysis = dspy.OutputField(desc="Detailed analysis")
    recommendation = dspy.OutputField(desc="Final recommendation")

@streamll.instrument(stream_fields=['analysis', 'recommendation'])
class CustomModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(CustomSignature)
```

## Consuming Token Events

### In Terminal (Default)

Tokens automatically stream to terminal with the default sink:

```
[TOKEN] answer: "Machine"
[TOKEN] answer: " learning"
[TOKEN] answer: " is"
[TOKEN] answer: " a"
[TOKEN] answer: " subset"
...
```

### In Custom Sinks

```python
from streamll.sinks.base import BaseSink
from streamll.core.events import TokenEvent

class TokenCollector(BaseSink):
    def __init__(self):
        super().__init__()
        self.tokens = []
    
    def handle_event(self, event):
        if isinstance(event, TokenEvent):
            self.tokens.append(event)
            print(f"Token #{event.token_index}: {event.token}")
    
    def get_text(self, field=None):
        """Reconstruct text from tokens."""
        if field:
            tokens = [e.token for e in self.tokens if e.data.get('field') == field]
        else:
            tokens = [e.token for e in self.tokens]
        return ''.join(tokens)
```

### In Consumers

```python
from streamll.consumer import RedisStreamConsumer

async def handle_token(event):
    if event.event_type == "token":
        field = event.data.get("field")
        token = event.token
        index = event.token_index
        
        # Update UI in real-time
        update_ui_field(field, token, index)
        
        # Stream to websocket
        await websocket.send_json({
            "type": "token",
            "field": field,
            "token": token,
            "index": index
        })

consumer = RedisStreamConsumer(url="redis://localhost:6379")
consumer.subscribe(handle_token)
```

## Model Compatibility

Token streaming requires the LLM provider to support streaming APIs:

| Provider | Streaming Support | Notes |
|----------|------------------|-------|
| OpenAI GPT-4/3.5 | ✅ Excellent | True token-by-token streaming |
| Anthropic Claude | ✅ Excellent | True token-by-token streaming |
| OpenRouter | ✅ Good | Depends on underlying model |
| Google Gemini 2.5 | ⚠️ Limited | Often returns full response as one chunk |
| Google Gemini 1.5 | ⚠️ Partial | Streams in large chunks, not tokens |
| Local Models (Ollama) | ✅ Good | True streaming with most models |

### Testing Your Model

```python
# Test if your model supports streaming
import dspy
from dspy.streaming import streamify, StreamListener

lm = dspy.LM("your-model", api_key="...")
dspy.settings.configure(lm=lm)

predictor = dspy.Predict("question -> answer")
listener = StreamListener(signature_field_name="answer")

streaming_predictor = streamify(
    predictor,
    stream_listeners=[listener],
    async_streaming=False
)

# If you see multiple chunks, streaming works
for chunk in streaming_predictor(question="Count to 5"):
    print(f"Chunk: {chunk}")
```

## Performance Considerations

### Overhead

Token streaming adds minimal overhead:
- ~1ms per token for event emission
- Events are buffered and sent asynchronously
- No impact on LLM response time

### Buffering

Tokens are buffered before sending to sinks:

```python
from streamll.sinks import RedisSink

sink = RedisSink(
    url="redis://localhost:6379",
    buffer_size=100,  # Buffer up to 100 tokens
    flush_interval=0.1,  # Flush every 100ms
)
```

### High-Volume Streaming

For applications with many concurrent streams:

```python
# Use larger buffers and batch sizes
sink = RedisSink(
    buffer_size=5000,
    batch_size=500,
    flush_interval=0.5
)

# Consider using RabbitMQ for better queue management
sink = RabbitMQSink(
    url="amqp://localhost",
    exchange="tokens",
    prefetch_count=1000
)
```

## Advanced Usage

### Conditional Streaming

Only stream for certain conditions:

```python
@streamll.instrument
class AdaptiveStreaming(dspy.Module):
    def __init__(self, stream_long_responses=True):
        super().__init__()
        self.stream_long = stream_long_responses
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        # Dynamically set streaming based on question complexity
        if self.stream_long and len(question) > 100:
            # This would need custom implementation
            self._streamll_stream_fields = ['answer']
        else:
            self._streamll_stream_fields = []
        
        return self.predict(question=question)
```

### Token Processing

Process tokens as they arrive:

```python
from streamll import emit_event
from streamll.core.events import StreamllEvent

@streamll.instrument(stream_fields=['answer'])
class ProcessingQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
        self.token_count = 0
    
    def forward(self, question):
        # Set up token processing
        result = self.predict(question=question)
        
        # Emit summary event
        emit_event(StreamllEvent(
            event_type="token.summary",
            data={"total_tokens": self.token_count}
        ))
        
        return result
```

### Multi-Language Support

Handle tokens in different languages:

```python
@streamll.instrument(stream_fields=['translation'])
class Translator(dspy.Module):
    def __init__(self):
        self.translate = dspy.Predict("text, target_language -> translation")
    
    def forward(self, text, target_lang):
        # Tokens will stream even for non-English languages
        return self.translate(text=text, target_language=target_lang)

# Streaming works with Unicode
translator = Translator()
result = translator("Hello world", "日本語")
# Streams: "こ", "ん", "に", "ち", "は", "世", "界"
```

## Troubleshooting

### No Tokens Received

1. Check model compatibility (see table above)
2. Ensure `stream_fields` matches actual output field names
3. Verify sink is started: `sink.start()`
4. Check DSPy cache isn't returning cached results: `cache=False`

### Tokens Arrive in Large Chunks

Some models (like Gemini) don't support true token streaming. Consider:
- Using a different model
- Accepting chunk-based streaming
- Implementing client-side token splitting

### Missing Fields

```python
# Debug: Check available fields
print(f"Output fields: {predictor.signature.output_fields}")

# For ChainOfThought
print(f"CoT fields: {cot.predict.signature.output_fields}")
```

## Examples

Find complete examples in our repository:

- `examples/token_streaming_basic.py` - Simple token streaming
- `examples/token_streaming_cot.py` - ChainOfThought with reasoning
- `examples/token_streaming_multi.py` - Multiple predictors
- `examples/token_streaming_websocket.py` - Stream to websocket
- `examples/token_streaming_ui.py` - Real-time UI updates