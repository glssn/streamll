# Custom Events in StreamLL

StreamLL allows you to emit custom events at any point in your DSPy pipeline, giving you fine-grained observability into your application's behavior.

## Quick Example

```python
from streamll import emit_event
from streamll.core.events import StreamllEvent, generate_event_id, get_execution_id
from datetime import datetime, UTC

# Emit a custom event
emit_event(StreamllEvent(
    event_id=generate_event_id(),
    execution_id=get_execution_id(),
    timestamp=datetime.now(UTC),
    event_type="my_custom_event",  # Your custom type
    module_name="MyModule",
    method_name="forward",
    data={
        "custom_field": "custom_value",
        "metrics": {"accuracy": 0.95}
    }
))
```

## Common Use Cases

### 1. RAG Pipeline Events

Track each stage of a retrieval-augmented generation pipeline:

```python
import streamll
from streamll import emit_event
from streamll.core.events import StreamllEvent, generate_event_id, get_execution_id
from datetime import datetime, UTC

@streamll.instrument
class RAGPipeline(dspy.Module):
    def forward(self, question):
        # Retrieval start
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="rag.retrieval.start",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={"query": question}
        ))
        
        docs = self.retrieve(question)
        
        # Retrieval complete
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="rag.retrieval.complete",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={
                "query": question,
                "num_docs": len(docs),
                "doc_ids": [doc.id for doc in docs]
            }
        ))
        
        # Reranking
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="rag.reranking",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={"num_docs": len(docs)}
        ))
        
        reranked = self.rerank(docs)
        
        # Generation
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="rag.generation.start",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={"context_size": sum(len(d.text) for d in reranked)}
        ))
        
        return self.generate(context=reranked, question=question)
```

### 2. Data Processing Events

Track data transformations and processing steps:

```python
@streamll.instrument
class DataProcessor(dspy.Module):
    def forward(self, data):
        # Validation
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="data.validation",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={
                "input_size": len(data),
                "valid": self.validate(data)
            }
        ))
        
        # Cleaning
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="data.cleaning",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={"removed_count": self.get_removed_count(data)}
        ))
        
        cleaned = self.clean(data)
        
        # Transformation
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="data.transformation",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={
                "input_size": len(cleaned),
                "output_format": "structured"
            }
        ))
        
        return self.transform(cleaned)
```

### 3. Model Selection Events

Track which models are being used and why:

```python
@streamll.instrument
class AdaptiveModule(dspy.Module):
    def forward(self, task):
        complexity = self.assess_complexity(task)
        
        if complexity < 0.3:
            model = "gpt-3.5-turbo"
        elif complexity < 0.7:
            model = "gpt-4"
        else:
            model = "gpt-4-turbo"
        
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="model.selection",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={
                "complexity_score": complexity,
                "selected_model": model,
                "reason": f"Complexity {complexity:.2f}"
            }
        ))
        
        return self.process_with_model(task, model)
```

### 4. Performance Monitoring

Track performance metrics throughout execution:

```python
import time

@streamll.instrument
class PerformanceAwareModule(dspy.Module):
    def forward(self, input_data):
        start_time = time.time()
        
        # Process
        result = self.process(input_data)
        
        duration = time.time() - start_time
        
        emit_event(StreamllEvent(
            event_id=generate_event_id(),
            execution_id=get_execution_id(),
            timestamp=datetime.now(UTC),
            event_type="performance.metrics",
            module_name=self.__class__.__name__,
            method_name="forward",
            data={
                "duration_seconds": duration,
                "input_size": len(input_data),
                "throughput": len(input_data) / duration,
                "memory_usage_mb": self.get_memory_usage()
            }
        ))
        
        return result
```

## Event Type Naming Conventions

Use dot-notation for hierarchical event types:

```python
# Good event type names
"retrieval.start"
"retrieval.complete"
"retrieval.error"
"generation.token"
"generation.complete"
"cache.hit"
"cache.miss"
"validation.passed"
"validation.failed"

# Domain-specific prefixes
"rag.retrieval.start"
"chat.message.received"
"agent.action.selected"
"tool.execution.start"
```

## Helper Function for Custom Events

Create a helper to reduce boilerplate:

```python
from streamll import emit_event
from streamll.core.events import StreamllEvent, generate_event_id, get_execution_id
from datetime import datetime, UTC

def emit_custom(event_type: str, data: dict, module_name: str = "Unknown"):
    """Helper to emit custom events with less boilerplate."""
    emit_event(StreamllEvent(
        event_id=generate_event_id(),
        execution_id=get_execution_id(),
        timestamp=datetime.now(UTC),
        event_type=event_type,
        module_name=module_name,
        method_name="forward",
        data=data
    ))

# Usage
emit_custom("retrieval.start", {"query": question})
emit_custom("cache.hit", {"key": cache_key, "size": 1024})
```

## Processing Custom Events

### In Consumers

```python
from streamll.consumer import RedisStreamConsumer

consumer = RedisStreamConsumer(url="redis://localhost:6379")

async def handle_event(event):
    # Handle different event types
    if event.event_type.startswith("rag."):
        handle_rag_event(event)
    elif event.event_type.startswith("performance."):
        update_metrics(event)
    elif event.event_type == "error":
        alert_on_error(event)
    else:
        # Handle other custom events
        log_event(event)

def handle_rag_event(event):
    if event.event_type == "rag.retrieval.complete":
        num_docs = event.data.get("num_docs", 0)
        if num_docs == 0:
            alert("No documents retrieved!")
        
def update_metrics(event):
    if event.event_type == "performance.metrics":
        metrics.record(
            duration=event.data["duration_seconds"],
            throughput=event.data["throughput"]
        )

consumer.subscribe(handle_event)
consumer.start()
```

### Real-time Dashboards

```python
# Send custom events to monitoring dashboards
def process_for_grafana(event):
    if event.event_type == "performance.metrics":
        grafana_client.send_metric(
            name="dspy.throughput",
            value=event.data["throughput"],
            tags={"module": event.module_name}
        )
```

## Best Practices

1. **Use Consistent Naming**: Adopt a naming convention for event types
2. **Include Context**: Add relevant data that helps with debugging
3. **Don't Over-Emit**: Balance observability with performance
4. **Structure Data**: Use consistent field names across similar events
5. **Document Events**: Keep a registry of your custom event types

## Event Data Guidelines

```python
# Good: Structured, consistent data
emit_event(StreamllEvent(
    event_type="retrieval.complete",
    data={
        "query": question,
        "num_results": len(results),
        "duration_ms": duration * 1000,
        "source": "vector_db",
        "metadata": {
            "index": "products",
            "similarity_threshold": 0.8
        }
    }
))

# Avoid: Unstructured, inconsistent data
emit_event(StreamllEvent(
    event_type="retrieval",
    data={
        "q": question,  # Inconsistent naming
        "n": len(results),  # Unclear abbreviation
        "time": duration,  # Missing units
        # Missing useful context
    }
))
```

## Performance Considerations

Custom events are buffered and sent asynchronously, so they have minimal impact on your application's performance:

- Events are queued in memory (default buffer: 1000 events)
- Sent in batches to sinks (default batch: 100 events)
- Circuit breakers prevent sink failures from affecting your app

Configure buffering for high-volume applications:

```python
from streamll.sinks import RedisSink

sink = RedisSink(
    url="redis://localhost:6379",
    buffer_size=5000,  # Larger buffer for high volume
    flush_interval=0.5,  # Flush every 500ms
    batch_size=500  # Larger batches
)
```

## Examples Repository

Find more examples in our [examples directory](https://github.com/streamll/streamll/tree/main/examples):

- `examples/rag_with_events.py` - Complete RAG pipeline with custom events
- `examples/performance_monitoring.py` - Performance tracking example
- `examples/multi_stage_pipeline.py` - Complex pipeline with stage events
- `examples/adaptive_routing.py` - Dynamic model selection with events