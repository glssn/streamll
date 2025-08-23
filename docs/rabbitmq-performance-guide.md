# RabbitMQ Production & Performance Guide

RabbitMQ sink provides reliable messaging and complex routing for DSPy observability with enterprise-grade features.

## Why Choose RabbitMQ for DSPy Observability?

RabbitMQ excels for DSPy applications when you need:

**✅ Complex Event Routing**: Route DSPy events by module type, error severity, or custom logic  
**✅ Guaranteed Delivery**: Publisher confirms ensure no DSPy event loss  
**✅ Dead Letter Queues**: Handle failed DSPy events gracefully  
**✅ Enterprise Integration**: AMQP protocol integrates with enterprise systems  
**✅ Flexible Consumers**: Multiple consumer patterns for different teams  

**❌ Choose Kafka Instead If**: You need >50K events/sec or event replay capabilities  
**❌ Choose Redis Instead If**: You need real-time analytics or caching integration  

## Quick Start (Reliable Defaults)

```python
from streamll.sinks.rabbitmq import RabbitMQSink

# Production-ready defaults prioritize reliability
sink = RabbitMQSink(
    amqp_url="amqp://user:pass@localhost:5672/",
    exchange="streamll_events",
    routing_key="streamll.{event_type}.{operation}"
)
```

**These defaults ensure:**
- ✅ No event loss (publisher confirms enabled)
- ✅ Survives broker restarts (durable exchanges/queues)  
- ✅ Good performance (moderate batching)
- ✅ Predictable behavior (traditional queues)

## Performance vs Reliability Matrix

| Use Case | Configuration | Performance | Reliability | When to Use |
|----------|---------------|-------------|-------------|-------------|
| **Development** | `publisher_confirms=False`<br>`durable=False` | ⚡⚡⚡ | ⚠️ | Local testing, rapid iteration |
| **Production** | **Defaults** | ⚡⚡ | ✅✅✅ | Most observability workloads |
| **High-Throughput** | `use_streams=True`<br>`batch_size=500` | ⚡⚡⚡ | ✅✅ | >10k events/sec, can accept small data loss |
| **Mission-Critical** | `batch_size=1`<br>`confirm_timeout=60` | ⚡ | ✅✅✅ | Financial, audit, compliance data |

## Configuration Reference

### Core Performance Settings

#### `publisher_confirms: bool = True`
**Reliability vs Performance tradeoff**

```python
# Reliable (default) - guarantees message persistence
sink = RabbitMQSink(publisher_confirms=True)   # ~2x slower, no data loss

# Fast - better performance, small risk of data loss  
sink = RabbitMQSink(publisher_confirms=False)  # ~2x faster, potential data loss
```

**Use `False` when:**
- Development/testing environments
- High-frequency, non-critical telemetry (metrics, traces)
- You have other reliability mechanisms (retries, multiple sinks)

#### `batch_size: int = 50` & `batch_timeout: float = 0.1`
**Network efficiency optimization**

```python
# Latency-optimized - small batches
sink = RabbitMQSink(batch_size=10, batch_timeout=0.01)   # Low latency

# Throughput-optimized - large batches  
sink = RabbitMQSink(batch_size=500, batch_timeout=1.0)   # High throughput

# Balanced (default)
sink = RabbitMQSink(batch_size=50, batch_timeout=0.1)    # Good compromise
```

**Performance Impact:**
- Larger batches: +50-90% throughput, +latency
- Smaller batches: -latency, -throughput, +CPU overhead

### Advanced Performance Features

#### `use_streams: bool = False`
**RabbitMQ Streams for ultra-high throughput**

```python
# Traditional queues (default) - familiar, full feature set
sink = RabbitMQSink(use_streams=False)

# RabbitMQ Streams - optimized for append-only, high-throughput scenarios  
sink = RabbitMQSink(
    use_streams=True,
    stream_max_age_hours=24,        # Auto-expire old data
    stream_max_segment_size="500MB", # Disk usage control
)
```

**Streams Benefits:**
- 5-10x higher throughput for append-only workloads
- Built-in partitioning and offset tracking
- Optimized disk I/O patterns

**Streams Limitations:**  
- No traditional queue features (TTL, DLQ, etc.)
- Less operational tooling
- Requires RabbitMQ 3.9+

#### `connection_pool_size: int = 5`
**Resource optimization**

```python
# Single connection - predictable, simple
sink = RabbitMQSink(connection_pool_size=1)

# Connection pooling (default) - better resource utilization
sink = RabbitMQSink(connection_pool_size=5)  

# High concurrency - for multiple sinks or high event rates
sink = RabbitMQSink(connection_pool_size=20)
```

### Durability vs Performance

#### `durable: bool = True`
**Persistence tradeoffs**

```python
# Persistent (default) - survives broker restarts
sink = RabbitMQSink(durable=True)    # ~20% slower, survives restarts

# In-memory - faster but data lost on restart  
sink = RabbitMQSink(durable=False)   # ~20% faster, data lost on restart
```

#### `message_ttl: int | None = None`
**Memory management**

```python
# No expiration (default) - permanent storage
sink = RabbitMQSink(message_ttl=None)

# Auto-expire - prevents memory/disk growth
sink = RabbitMQSink(message_ttl=3600)  # 1 hour retention
```

## Performance Recipes

### Recipe 1: Development Environment
```python
# Fast iteration, don't care about data loss
sink = RabbitMQSink(
    amqp_url="amqp://localhost:5672/",
    publisher_confirms=False,  # Skip reliability overhead
    durable=False,            # In-memory only
    batch_size=100,           # Large batches for speed
    message_ttl=300,          # 5min cleanup
)
```

### Recipe 2: Production Observability  
```python
# Balanced reliability + performance (DEFAULT)
sink = RabbitMQSink(
    amqp_url="amqp://user:pass@rabbitmq:5672/production",
    # All defaults are production-ready
    exchange="observability",
    routing_key="app.{module_name}.{event_type}",
)
```

### Recipe 3: High-Throughput Analytics
```python
# Optimized for >10k events/sec
sink = RabbitMQSink(
    amqp_url="amqp://user:pass@rabbitmq:5672/analytics", 
    use_streams=True,         # Stream-optimized
    batch_size=500,          # Large batches
    batch_timeout=0.5,       # Accept higher latency
    publisher_confirms=True,  # Still want reliability
    stream_max_age_hours=6,  # Retain 6 hours
)
```

### Recipe 4: Mission-Critical Audit Trail
```python
# Maximum reliability, latency acceptable
sink = RabbitMQSink(
    amqp_url="amqp://user:pass@rabbitmq:5672/audit",
    batch_size=1,            # Immediate publishing
    confirm_timeout=60.0,    # Patient confirmation waits
    publisher_confirms=True,  # Guaranteed delivery
    durable=True,           # Full persistence
    connection_pool_size=1, # Predictable connections
)
```

## Benchmarking Your Configuration

### Basic Throughput Test
```python
import time
from streamll.models import StreamllEvent

# Create test events
events = [
    StreamllEvent(
        execution_id=f"benchmark-{i}",
        event_type="benchmark", 
        operation="throughput_test",
        data={"index": i}
    ) for i in range(1000)
]

# Measure throughput
sink.start()
start_time = time.time()

for event in events:
    sink.handle_event(event)
    
sink.flush()  # Ensure all published
duration = time.time() - start_time
throughput = len(events) / duration

print(f"Throughput: {throughput:.1f} events/sec")
sink.stop()
```

### Latency Measurement
```python
# Measure end-to-end latency with small batches
sink = RabbitMQSink(batch_size=1, batch_timeout=0.001)

start_time = time.time()
sink.handle_event(test_event)
sink.flush()
latency = time.time() - start_time

print(f"End-to-end latency: {latency*1000:.1f}ms")
```

## Troubleshooting Performance Issues

### Symptom: Low Throughput
**Check:**
1. `batch_size` too small → Increase to 100-500
2. `publisher_confirms=True` → Try `False` if acceptable
3. `durable=True` on fast storage → Consider `False` for temporary data
4. Network latency → Use larger batches, connection pooling

### Symptom: High Latency  
**Check:**
1. `batch_timeout` too high → Reduce to 0.01-0.1s
2. `batch_size` too large → Reduce to 1-10 for real-time
3. `confirm_timeout` too high → Reduce if confirms enabled

### Symptom: Memory Growth
**Check:**
1. `message_ttl=None` → Set expiration time  
2. Consumer not keeping up → Scale consumers or increase `prefetch_count`
3. `connection_pool_size` too high → Reduce if many sinks

### Symptom: Connection Errors
**Check:**
1. `connection_pool_size` too high → Reduce pool size
2. Network instability → Enable circuit breaker
3. RabbitMQ resource limits → Check broker configuration

## Monitoring & Observability

### Key Metrics to Track
```python
# Add monitoring to your sink
sink = RabbitMQSink(
    # ... configuration ...
    metrics_callback=lambda stats: print(f"Published {stats['events_sent']} events")
)
```

**Monitor:**
- Events/second throughput
- End-to-end latency (publish to confirm)
- Queue depth (if using traditional queues)
- Connection pool utilization
- Publisher confirm failure rate

### RabbitMQ Management Integration
```bash
# Monitor queue metrics via HTTP API
curl -u guest:guest http://localhost:15672/api/queues/vhost/streamll_events

# Monitor exchange routing
curl -u guest:guest http://localhost:15672/api/exchanges/vhost/streamll_events
```

## Migration Path

### From Basic to Optimized Configuration

1. **Start with defaults** - Ensure correctness first
2. **Measure baseline** - Get current throughput/latency numbers  
3. **Tune incrementally** - Change one setting at a time
4. **Validate correctness** - Ensure no data loss after changes
5. **Monitor in production** - Watch for regressions

### Common Migration Steps
```python
# Step 1: Baseline (defaults)
sink = RabbitMQSink()

# Step 2: Increase batch size  
sink = RabbitMQSink(batch_size=100)

# Step 3: Tune timeouts
sink = RabbitMQSink(batch_size=100, batch_timeout=0.2)

# Step 4: Consider streams for high throughput
sink = RabbitMQSink(batch_size=100, batch_timeout=0.2, use_streams=True)
```

## Cloud Provider Integration

### Amazon MQ for RabbitMQ

#### Managed RabbitMQ Configuration
```python
from streamll.sinks.rabbitmq import RabbitMQSink

# Amazon MQ cluster endpoint
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqps://username:password@b-abc123-456.mq.us-east-1.amazonaws.com:5671/",
    exchange="dspy_production_events",
    routing_key="dspy.{module_name}.{event_type}",
    
    # Amazon MQ optimizations
    durable=True,               # Persist across broker restarts
    publisher_confirms=True,    # Guaranteed delivery
    connection_pool_size=5,     # AWS handles connection limits
    
    # SSL required for Amazon MQ
    ssl=True,
    ssl_verify=True
)
```

#### Environment Variables for Amazon MQ
```bash
# Amazon MQ connection details
export AMAZON_MQ_URL="amqps://username:password@b-abc123-456.mq.us-east-1.amazonaws.com:5671/"
export AMAZON_MQ_EXCHANGE="dspy_production_events"
export AWS_DEFAULT_REGION="us-east-1"

# StreamLL configuration
export RABBITMQ_ROUTING_KEY="dspy.{module_name}.{event_type}"
export RABBITMQ_DURABLE="true"
```

```python
import os
from streamll.sinks.rabbitmq import RabbitMQSink

rabbitmq_sink = RabbitMQSink(
    amqp_url=os.getenv("AMAZON_MQ_URL"),
    exchange=os.getenv("AMAZON_MQ_EXCHANGE"),
    routing_key=os.getenv("RABBITMQ_ROUTING_KEY"),
    durable=os.getenv("RABBITMQ_DURABLE", "true").lower() == "true"
)
```

### CloudAMQP (Managed RabbitMQ)

#### CloudAMQP Configuration
```python
from streamll.sinks.rabbitmq import RabbitMQSink

# CloudAMQP connection URL
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqps://username:password@instancename.cloudamqp.com/vhost",
    exchange="dspy_events",
    routing_key="streamll.{operation}.{event_type}",
    
    # CloudAMQP optimizations
    batch_size=50,              # Smaller batches for shared infrastructure
    batch_timeout=0.1,          # Quick publishing
    publisher_confirms=True,    # Ensure delivery
    
    # Connection limits for shared hosting
    connection_pool_size=3,
    max_retries=5
)
```

#### CloudAMQP Environment Setup
```bash
# CloudAMQP connection (from CloudAMQP console)
export CLOUDAMQP_URL="amqps://username:password@instancename.cloudamqp.com/vhost"
export CLOUDAMQP_EXCHANGE="dspy_events"

# Performance settings for shared hosting
export RABBITMQ_BATCH_SIZE="50"
export RABBITMQ_CONNECTION_POOL="3"
```

### Azure Service Bus (AMQP 1.0 Compatible)

#### Service Bus Queue Configuration
```python
from streamll.sinks.rabbitmq import RabbitMQSink

# Azure Service Bus with AMQP 1.0
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqps://your-namespace.servicebus.windows.net",
    exchange="",  # Service Bus uses queues, not exchanges
    routing_key="dspy-events",  # Queue name
    
    # Azure Service Bus authentication
    username="SharedAccessKeyName",
    password="SharedAccessKey",
    
    # Service Bus optimizations
    batch_size=30,              # Service Bus message limits
    message_ttl=3600,          # 1 hour retention
    durable=True,              # Persist messages
    
    # AMQP 1.0 specific
    amqp_version="1.0"
)
```

#### Managed Identity for Azure Service Bus
```python
from azure.identity import DefaultAzureCredential
from streamll.sinks.rabbitmq import RabbitMQSink

# Using managed identity (no secrets in code)
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqps://your-namespace.servicebus.windows.net",
    routing_key="dspy-events",
    
    # Managed identity authentication
    auth_provider="azure_managed_identity",
    credential=DefaultAzureCredential(),
    
    # Azure optimizations
    batch_size=30,
    publisher_confirms=True
)
```

### Google Cloud Pub/Sub (via AMQP Bridge)

#### Pub/Sub with AMQP Protocol
```python
from streamll.sinks.rabbitmq import RabbitMQSink

# Google Cloud Pub/Sub AMQP endpoint
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqps://your-project.pubsub-amqp.googleapis.com:5671",
    exchange="dspy-events-topic",  # Pub/Sub topic
    routing_key="",  # Not used in Pub/Sub
    
    # GCP authentication
    username="your-service-account@project.iam.gserviceaccount.com",
    password="service-account-key",
    
    # Pub/Sub optimizations
    batch_size=100,             # Pub/Sub handles batching well
    compression_type="gzip",    # Reduce network usage
    publisher_confirms=True,    # At-least-once delivery
    
    # GCP-specific settings
    ssl=True,
    connection_timeout=30
)
```

## DSPy Integration Patterns

### Pattern 1: Error-Based Routing

Route DSPy events to different queues based on severity:

```python
import streamll
from streamll.sinks.rabbitmq import RabbitMQSink

# Error events go to high-priority queue
error_sink = RabbitMQSink(
    amqp_url="amqp://localhost:5672/",
    exchange="dspy_events",
    routing_key="errors.{module_name}",  # errors.RAGModule
    queue_priority=10  # High priority
)

# Normal events go to standard queue  
normal_sink = RabbitMQSink(
    amqp_url="amqp://localhost:5672/",
    exchange="dspy_events", 
    routing_key="events.{module_name}",  # events.RAGModule
    queue_priority=1   # Normal priority
)

# Configure different sinks for different event types
streamll.configure(
    sinks=[error_sink, normal_sink],
    event_filter={"start", "end", "error"}  # All event types
)

# RabbitMQ routes events based on routing keys
class RAGModule(dspy.Module):
    def forward(self, question):
        # Error events → errors.RAGModule queue
        # Start/end events → events.RAGModule queue
        return self.process(question)
```

### Pattern 2: Module-Specific Consumers

Different teams consume events from their modules:

```python
# Team A: RAG module events
rag_sink = RabbitMQSink(
    amqp_url="amqp://rabbitmq:5672/",
    exchange="team_events",
    routing_key="rag.{event_type}",     # rag.start, rag.end, rag.error
    dead_letter_exchange="dlx_rag"      # Failed messages
)

# Team B: Classification module events
classifier_sink = RabbitMQSink(
    amqp_url="amqp://rabbitmq:5672/",
    exchange="team_events",
    routing_key="classify.{event_type}", # classify.start, classify.end
    dead_letter_exchange="dlx_classify"
)

# Consumer binds to specific routing patterns
# rag.* → RAG team gets all RAG events
# classify.* → Classification team gets their events
```

### Pattern 3: Dead Letter Queue for Failed DSPy Events

Handle DSPy events that fail processing:

```python
from streamll.sinks.rabbitmq import RabbitMQSink

rabbitmq_sink = RabbitMQSink(
    amqp_url="amqp://localhost:5672/",
    exchange="dspy_events",
    routing_key="dspy.{module_name}.{event_type}",
    
    # Dead letter configuration
    dead_letter_exchange="dspy_failed",
    dead_letter_routing_key="failed.{module_name}",
    message_ttl=300,  # 5 minutes before DLQ
    
    # Retry configuration
    max_retries=3,
    retry_backoff_ms=1000  # Exponential backoff
)

# Consumer for failed events (alerting, debugging)
class FailedEventConsumer:
    def handle_failed_dspy_event(self, event):
        # Send alert to monitoring system
        # Log detailed failure information
        # Potentially retry with different parameters
        pass
```

---

**Remember:** Follow the Diamond Approach
1. **Reliability first** - Get correctness with defaults
2. **Consistency second** - Ensure predictable behavior  
3. **Performance third** - Optimize after reliability is proven