# Token Streaming

streamll provides real-time token streaming for DSPy modules, showing LLM responses as they're generated.

## Quick Start

```python
import streamll
import dspy

@streamll.instrument(stream_fields=['answer'])
class SimpleQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)

qa = SimpleQA()
result = qa("What is machine learning?")
```

## How It Works

streamll uses the LLM's streaming API to emit token events with:

- `token`: The text chunk  
- `token_index`: Position in the stream
- `field`: Which output field (e.g., 'answer')
- `finish_reason`: Why streaming stopped

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

### Custom Signatures

```python
class QASignature(dspy.Signature):
    """Answer questions with analysis."""
    question = dspy.InputField() 
    analysis = dspy.OutputField()
    answer = dspy.OutputField()

@streamll.instrument(stream_fields=['analysis', 'answer'])
class QAModule(dspy.Module):
    def __init__(self):
        self.predict = dspy.Predict(QASignature)
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

consumer = RedisStreamConsumer(url="redis://localhost:6379")
await consumer.start()

# Process events one by one
while True:
    event = await consumer.consume_one()
    if event and event.event_type == "token":
        field = event.data.get("field")
        token = event.data.get("token")
        index = event.data.get("token_index") 
        print(f"Token #{index} for {field}: {token}")

await consumer.stop()
```


## Advanced: Dynamic Streaming

You can modify streaming behavior dynamically:

```python
@streamll.instrument
class AdaptiveStreaming(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        # Enable streaming for complex questions
        if len(question) > 50:
            self._streamll_stream_fields = ['answer']
        else:
            self._streamll_stream_fields = []
        
        return self.predict(question=question)
```

## Troubleshooting

**No tokens received?**
- Ensure `stream_fields` matches your output field names
- Check that sink is started: `sink.start()` 
- Some models return responses in large chunks rather than individual tokens

**Finding available fields:**
```python
# Check what fields you can stream
predict = dspy.Predict("question -> answer")
print(predict.signature.output_fields.keys())  # ['answer']

cot = dspy.ChainOfThought("question -> answer") 
print(cot.predict.signature.output_fields.keys())  # ['reasoning', 'answer']
```
