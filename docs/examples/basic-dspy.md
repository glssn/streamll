# Basic DSPy Integration

Learn how to add StreamLL monitoring to any DSPy module with simple examples.

## Simple Question Answering

The most basic DSPy pattern - a single LLM call:

```python
import streamll
import dspy

@streamll.instrument
class SimpleQA(dspy.Module):
    """Simple question answering with StreamLL monitoring."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)

# Configure DSPy
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash"))

# Use it
qa = SimpleQA()
result = qa("What is the capital of France?")
```

**StreamLL Output:**
```bash
[16:45:23.123] ▶ module_forward [SimpleQA] (a1b2c3d4)
[16:45:23.124] ▶ llm_call (e5f6g7h8)
[16:45:25.456] ■ llm_call (e5f6g7h8)
[16:45:25.457] ■ module_forward [SimpleQA] (a1b2c3d4)
```

## Chain of Thought Reasoning

Monitor multi-step reasoning:

```python
@streamll.instrument
class ChainOfThoughtQA(dspy.Module):
    """Question answering with explicit reasoning steps."""

    def __init__(self):
        super().__init__()
        self.cot = dspy.ChainOfThought("question -> reasoning, answer")

    def forward(self, question):
        return self.cot(question=question)

# Usage
cot_qa = ChainOfThoughtQA()
result = cot_qa("If a train leaves Chicago at 60mph heading to New York 800 miles away, how long will it take?")

print(f"Reasoning: {result.reasoning}")
print(f"Answer: {result.answer}")
```

**StreamLL shows the reasoning process:**

```bash
[16:46:12.234] ▶ module_forward [ChainOfThoughtQA] (b2c3d4e5)
[16:46:12.235] ▶ llm_call (f6g7h8i9)
# LLM generates reasoning and answer...
[16:46:15.678] ■ llm_call (f6g7h8i9)
[16:46:15.679] ■ module_forward [ChainOfThoughtQA] (b2c3d4e5)
```

## Multi-Step Pipeline

Monitor complex pipelines with multiple LLM calls:

```python
@streamll.instrument
class AnalysisPipeline(dspy.Module):
    """Multi-step analysis pipeline."""

    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict("text -> summary")
        self.classify = dspy.Predict("text -> category") 
        self.score = dspy.Predict("text -> score")

    def forward(self, text):
        # Step 1: Summarize
        summary = self.summarize(text=text)

        # Step 2: Classify
        category = self.classify(text=text)

        # Step 3: Score
        score = self.score(text=text)

        return {
            "summary": summary.summary,
            "category": category.category, 
            "score": score.score
        }

# Usage
pipeline = AnalysisPipeline()
result = pipeline("This product is amazing! Great quality and fast shipping.")
```

**StreamLL shows each step:**
```bash
[16:47:01.111] ▶ module_forward [AnalysisFilter] (c3d4e5f6)
[16:47:01.112] ▶ llm_call (g7h8i9j0) # summarize
[16:47:02.333] ■ llm_call (g7h8i9j0)
[16:47:02.334] ▶ llm_call (k1l2m3n4) # classify  
[16:47:03.555] ■ llm_call (k1l2m3n4)
[16:47:03.556] ▶ llm_call (o5p6q7r8) # score
[16:47:04.777] ■ llm_call (o5p6q7r8)
[16:47:04.778] ■ module_forward [AnalysisFilter] (c3d4e5f6)
```

## Customizing Monitoring

### Filter Specific Operations

Only monitor certain types of operations:

```python
@streamll.instrument(
    operations=["summarization"],  # Only track operations named "summarization"
    include_outputs=False  # Don't log outputs (for privacy)
)
class PrivateAnalyzer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.summarize = dspy.Predict("document -> summary")
```

### Custom Sinks

Send events to specific destinations:

```python
from streamll.sinks import RedisSink, TerminalSink

@streamll.instrument(sinks=[
    TerminalSink(),  # Development debugging
    RedisSink("redis://prod:6379", stream_key="analysis_events")  # Production monitoring
])
class ProductionAnalyzer(dspy.Module):
    pass
```

### Multiple Modules

Each module gets isolated monitoring:

```python
@streamll.instrument(sinks=[RedisSink(stream_key="retrieval_events")])
class DocumentRetriever(dspy.Module):
    pass

@streamll.instrument(sinks=[RedisSink(stream_key="generation_events")])
class AnswerGenerator(dspy.Module):
    pass

# Each module streams to different Redis keys
retriever = DocumentRetriever()
generator = AnswerGenerator()
```

## Advanced Patterns

### Error Handling

StreamLL automatically captures errors:

```python
@streamll.instrument
class ErrorProneModule(dspy.Module):
    def forward(self, text):
        if not text:
            raise ValueError("Text cannot be empty")
        return self.predict(text=text)

try:
    result = ErrorProneModule()("")
except ValueError:
    pass  # StreamLL captured the error
```

**Error events in StreamLL:**
```bash
[16:48:15.123] ▶ module_forward [ErrorProneModule] (d4e5f6g7)
[16:48:15.124] ■ error (d4e5f6g7)
  {
    "error_type": "ValueError",
    "message": "Text cannot be empty",
    "traceback": "..."
  }
```

### Performance Monitoring

Track execution time automatically:

```python
@streamll.instrument
class SlowModule(dspy.Module):
    def forward(self, query):
        # StreamLL automatically tracks execution time
        import time
        time.sleep(1)  # Simulate slow operation
        return self.predict(query=query)
```

**Performance data in events:**
```bash
[16:49:01.000] ▶ module_forward [SlowModule] (e5f6g7h8)
[16:49:02.100] ■ module_forward [SlowModule] (e5f6g7h8)  # 1.1 second duration
  {
    "execution_time_ms": 1100,
    "outputs": "..."
  }
```

## Best Practices

### 1. Start Simple
Begin with just `@streamll.instrument` - no configuration needed.

### 2. Add Production Sinks Later
Use TerminalSink for development, add RedisSink for production.

### 3. Monitor What Matters
Use `operations` filter to focus on important parts of your pipeline.

### 4. Preserve Privacy
Use `include_outputs=False` for sensitive data.

### 5. Isolate Modules
Give each module its own sink configuration to avoid event mixing.

## Next Steps

- **[RAG Pipeline Example](rag-pipeline.md)** - Document retrieval + generation
- **[Token Streaming](streaming.md)** - Real-time token monitoring
- **[Production Deployment](../production/redis-sink.md)** - Scale to production
