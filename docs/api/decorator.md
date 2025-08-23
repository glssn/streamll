# Decorator API Reference

Complete reference for the `@streamll.instrument` decorator - the primary interface for adding observability to DSPy modules.

## Basic Usage

```python
import streamll

@streamll.instrument
class MyModule(dspy.Module):
    pass
```

## Full Signature

```python
@streamll.instrument(
    operations: list[str] | None = None,
    sinks: list[BaseSink] | None = None,
    include_inputs: bool = True,
    include_outputs: bool = True,
    event_filter: set[str] | None = None
)
```

## Parameters

### `operations` (optional)

Filter which operations to monitor by name.

```python
# Only monitor operations named "retrieval"
@streamll.instrument(operations=["retrieval"])
class RAGModule(dspy.Module):
    pass

# Monitor multiple specific operations
@streamll.instrument(operations=["embedding", "ranking", "generation"])
class AdvancedRAG(dspy.Module):
    pass
```

**Default**: `None` (monitor all operations)

### `sinks` (optional)

Custom sinks for this module's events.

```python
from streamll.sinks import RedisSink, TerminalSink

# Single sink
@streamll.instrument(sinks=[RedisSink("redis://localhost:6379")])
class ProductionModule(dspy.Module):
    pass

# Multiple sinks
@streamll.instrument(sinks=[
    TerminalSink(),  # Development debugging
    RedisSink("redis://prod:6379", stream_key="module_events")  # Production
])
class MonitoredModule(dspy.Module):
    pass
```

**Default**: `None` (uses auto-configured TerminalSink)

### `include_inputs` (optional)
Whether to capture input arguments in events.

```python
# Capture inputs (default)
@streamll.instrument(include_inputs=True)
class PublicModule(dspy.Module):
    pass

# Don't capture inputs (privacy)
@streamll.instrument(include_inputs=False)
class PrivateModule(dspy.Module):
    pass
```

**Default**: `True`

### `include_outputs` (optional)
Whether to capture output values in events.

```python
# Capture outputs (default)
@streamll.instrument(include_outputs=True)
class StandardModule(dspy.Module):
    pass

# Don't capture outputs (large responses)
@streamll.instrument(include_outputs=False)
class LargeResponseModule(dspy.Module):
    pass
```

**Default**: `True`

### `event_filter` (optional)
Filter which event types to emit.

```python
# Only emit error and performance events
@streamll.instrument(event_filter={"error", "performance"})
class CriticalModule(dspy.Module):
    pass

# Only LLM calls
@streamll.instrument(event_filter={"llm_call"})
class LLMOnlyModule(dspy.Module):
    pass
```

**Default**: `None` (emit all event types)

## Event Types Captured

The decorator automatically captures these event types:

| Event Type | Description | When Emitted |
|------------|-------------|--------------|
| `module_forward` | Module execution | Start/end of `forward()` method |
| `llm_call` | LLM API calls | Any LLM invocation via DSPy |
| `tool_call` | Tool usage | Retrievers, custom tools, APIs |
| `error` | Exceptions | Any unhandled exception |
| `token` | Token streaming | When streaming is enabled |

## Auto-Configuration

The decorator automatically configures StreamLL if no global configuration exists:

```python
# This automatically creates a TerminalSink
@streamll.instrument
class AutoConfiguredModule(dspy.Module):
    pass

# No auto-configuration if already configured
streamll.configure(sinks=[RedisSink("redis://localhost:6379")])

@streamll.instrument  # Uses existing configuration
class ConfiguredModule(dspy.Module):
    pass
```

## Multiple Decorators

Each module can have independent configuration:

```python
@streamll.instrument(sinks=[RedisSink(stream_key="retrieval_events")])
class RetrievalModule(dspy.Module):
    pass

@streamll.instrument(sinks=[RedisSink(stream_key="generation_events")])
class GenerationModule(dspy.Module):
    pass

# Isolated event streams
retriever = RetrievalModule()  # Events go to "retrieval_events"
generator = GenerationModule()  # Events go to "generation_events"
```

## Inheritance

Decorated classes work with inheritance:

```python
@streamll.instrument
class BaseModule(dspy.Module):
    def common_method(self):
        pass

class DerivedModule(BaseModule):  # Inherits monitoring
    def specific_method(self):
        pass

# Both modules are monitored
base = BaseModule()
derived = DerivedModule()
```

## Error Handling

The decorator handles errors gracefully:

```python
@streamll.instrument
class ErrorProneModule(dspy.Module):
    def forward(self, text):
        if not text:
            raise ValueError("Text required")  # Captured as error event
        return self.predict(text=text)

try:
    module = ErrorProneModule()
    result = module("")  # Raises ValueError
except ValueError:
    pass  # Error event already emitted
```

## Performance Impact

The decorator adds minimal overhead:

```python
import time

@streamll.instrument
class TimedModule(dspy.Module):
    def forward(self, query):
        time.sleep(0.1)  # Simulate work
        return self.predict(query=query)

# Decorator overhead: ~0.1ms per method call
# Measurement included in events automatically
```

## Advanced Patterns

### Conditional Monitoring

```python
import os

# Only monitor in production
if os.getenv("ENVIRONMENT") == "production":
    @streamll.instrument(sinks=[RedisSink("redis://prod:6379")])
    class ConditionalModule(dspy.Module):
        pass
else:
    class ConditionalModule(dspy.Module):  # No monitoring in dev
        pass
```

### Dynamic Configuration

```python
def create_monitored_module(config):
    sinks = []

    if config.get("debug"):
        sinks.append(TerminalSink())

    if config.get("redis_url"):
        sinks.append(RedisSink(config["redis_url"]))

    @streamll.instrument(sinks=sinks)
    class DynamicModule(dspy.Module):
        pass

    return DynamicModule

# Usage
config = {"debug": True, "redis_url": "redis://localhost:6379"}
ModuleClass = create_monitored_module(config)
module = ModuleClass()
```

### Module Composition

```python
@streamll.instrument(sinks=[RedisSink(stream_key="rag_retrieval")])
class Retriever(dspy.Module):
    pass

@streamll.instrument(sinks=[RedisSink(stream_key="rag_generation")])  
class Generator(dspy.Module):
    pass

@streamll.instrument(sinks=[RedisSink(stream_key="rag_pipeline")])
class RAGPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.retriever = Retriever()  # Independently monitored
        self.generator = Generator()  # Independently monitored

    def forward(self, query):
        docs = self.retriever(query)     # Events to "rag_retrieval"
        answer = self.generator(docs)    # Events to "rag_generation"
        return answer                    # Events to "rag_pipeline"
```

## Validation

The decorator validates configuration at class definition time:

```python
# ✅ Valid configurations
@streamll.instrument
@streamll.instrument()
@streamll.instrument(sinks=[TerminalSink()])
@streamll.instrument(include_inputs=False)

# ❌ Invalid configurations
@streamll.instrument
class NotDSPyModule:  # TypeError: must be dspy.Module subclass
    pass

@streamll.instrument
@streamll.instrument  # ValueError: already instrumented
class DoubleDecorated(dspy.Module):
    pass

@streamll.instrument(sinks=["not_a_sink"])  # TypeError: invalid sink type
class InvalidSink(dspy.Module):
    pass
```

## Debugging

Enable debug logging to troubleshoot decorator issues:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamll.decorator")

@streamll.instrument
class DebugModule(dspy.Module):
    pass

# See decorator activity in logs
module = DebugModule()
```

## Best Practices

1. **Start simple**: Use `@streamll.instrument` with no parameters
2. **Add sinks gradually**: Start with TerminalSink, add Redis for production
3. **Filter sensitive data**: Use `include_inputs=False` for privacy
4. **Separate concerns**: Use different sinks for different modules
5. **Monitor composition**: Each module in a pipeline can be independently monitored
6. **Handle errors**: Let the decorator capture exceptions automatically
7. **Test configuration**: Validate sinks and parameters work as expected

## Related APIs

- **[Sinks API](sinks.md)** - Available sink types and configuration
- **[Streaming API](streaming.md)** - Token-by-token streaming
- **[Context API](context.md)** - Manual event emission
