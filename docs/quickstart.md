# Quick Start Guide

Get StreamLL running with your DSPy application in 5 minutes.

## Prerequisites

- Python 3.11+
- DSPy installed (`pip install dspy`)
- A DSPy application or willingness to create a simple one

## Step 1: Install StreamLL

```bash
pip install streamll
```

## Step 2: Create a Simple DSPy Module

If you don't have a DSPy module yet, create this simple example:

```python
# simple_module.py
import dspy

class SimpleQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        return self.predict(question=question)

# Configure with your LLM (example with Gemini)
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash", api_key="your-api-key"))
```

## Step 3: Add StreamLL Monitoring

Add one import and one decorator:

```python
import streamll  # ← Add this import
import dspy

@streamll.instrument  # ← Add this decorator
class SimpleQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        return self.predict(question=question)

# Configure DSPy as usual
dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash", api_key="your-api-key"))
```

## Step 4: Run and See the Magic

```python
# Run your module
qa = SimpleQA()
result = qa("What is machine learning?")
print(f"Answer: {result.answer}")
```

**You'll see real-time output like this:**

```bash
[16:45:23.123] ▶ module_forward [SimpleQA] (a1b2c3d4)
  {
    "args": ["What is machine learning?"],
    "kwargs": {}
  }
[16:45:23.124] ▶ llm_call (e5f6g7h8)
[16:45:25.456] ■ llm_call (e5f6g7h8)
[16:45:25.457] ■ module_forward [SimpleQA] (a1b2c3d4)
  {
    "outputs": "Prediction(answer='Machine learning is a subset of...')"
  }

Answer: Machine learning is a subset of artificial intelligence...
```

## Step 5: Add Production Redis Sink (Optional)

For production monitoring, stream events to Redis:

```python
import streamll
from streamll.sinks import RedisSink
import dspy

# Configure Redis sink
@streamll.instrument(sinks=[
    RedisSink("redis://localhost:6379", stream_key="qa_events")
])
class SimpleQA(dspy.Module):
    # ... same as before
```

**Start Redis** (if you don't have it running):
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:alpine

# Or install locally
brew install redis && redis-server
```

## Step 6: View Events in Redis

```python
import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Read events from stream
entries = r.xread({"qa_events": "0"})
for stream_name, stream_entries in entries:
    for entry_id, fields in stream_entries:
        event = json.loads(fields["event"])
        print(f"Event: {event['event_type']} at {event['timestamp']}")
```

## 🎉 You're Done!

StreamLL is now monitoring your DSPy application. You'll see:

- **LLM calls** with prompts and responses
- **Module execution** with inputs and outputs  
- **Performance timing** for each operation
- **Error handling** if anything goes wrong

## Next Steps

### Enable Token Streaming

See individual tokens arrive in real-time:

```python
import streamll

# Wrap your module for token streaming
streaming_qa = streamll.create_streaming_wrapper(
    qa, 
    signature_field_name="answer"
)

# Watch tokens stream live
result = streaming_qa("Explain quantum computing")
```

### Explore More Examples

- **[RAG Pipeline](examples/rag-pipeline.md)** - Document retrieval + generation
- **[Multi-Module Apps](examples/multi-module.md)** - Complex DSPy applications
- **[Custom Events](examples/custom-events.md)** - Add your own monitoring

### Production Deployment

- **[Redis Configuration](production/redis-sink.md)** - Production Redis setup
- **[Monitoring & Alerts](production/monitoring.md)** - What to watch in production
- **[Performance Tuning](production/performance.md)** - Optimize for scale

## Troubleshooting

### Common Issues

**"Module not instrumented"**
- Make sure you have `@streamll.instrument` on your DSPy module class
- Check that you're importing `streamll` before defining the module

**"No output showing"**
- StreamLL auto-configures a TerminalSink - you should see output immediately
- Try adding `streamll.configure(sinks=[streamll.sinks.TerminalSink()])` explicitly

**"Redis connection failed"**
- Make sure Redis is running: `redis-cli ping` should return `PONG`
- Check your Redis URL is correct
- StreamLL will buffer events locally if Redis is down

### Need Help?

- **GitHub Issues**: [Report bugs or ask questions](https://github.com/streamll/streamll/issues)
- **Discord Community**: Join our community for real-time help
- **Documentation**: Browse our [complete documentation](../README.md)

---

**🚀 Happy monitoring!** You now have full observability into your DSPy applications.