# StreamLL Sink Comparison Guide

Choose the right sink for your DSPy observability needs. This guide helps you understand when to use Kafka, Redis, or RabbitMQ based on your specific requirements.

## Quick Decision Matrix

| Your Requirement | Best Sink | Alternative | Why |
|------------------|-----------|-------------|-----|
| **Real-time dashboards** | Redis | Kafka | Sub-millisecond event processing |
| **>100K events/sec** | Kafka | Redis Cluster | Highest throughput |
| **Complex event routing** | RabbitMQ | Kafka | Advanced routing patterns |
| **Event replay/debugging** | Kafka | Redis Streams | Persistent event log |
| **Simple pub/sub** | Redis | RabbitMQ | Minimal infrastructure |
| **Enterprise integration** | RabbitMQ | Kafka | AMQP protocol support |
| **Cost optimization** | Redis | RabbitMQ | Single service for cache + events |
| **Long-term retention** | Kafka | Redis | Built for log retention |

## Detailed Comparison

### Performance Characteristics

| Metric | Kafka | Redis | RabbitMQ |
|--------|-------|-------|----------|
| **Throughput** | 100K+ events/sec | 50K+ events/sec | 20K+ events/sec |
| **Latency** | 10-50ms | <1ms | 5-20ms |
| **Memory Usage** | Low | High | Medium |
| **Disk Usage** | High | Low | Medium |
| **CPU Usage** | Medium | Low | Medium |

### Operational Complexity

| Aspect | Kafka | Redis | RabbitMQ |
|--------|-------|-------|----------|
| **Setup Complexity** | High | Low | Medium |
| **Operational Overhead** | High | Low | Medium |
| **Scaling Difficulty** | Medium | Easy | Medium |
| **Monitoring** | Complex | Simple | Medium |
| **Debugging** | Hard | Easy | Medium |

### Feature Matrix

| Feature | Kafka | Redis | RabbitMQ |
|---------|-------|-------|----------|
| **Event Persistence** | ✅ Excellent | ⚠️ Memory-based | ✅ Good |
| **Event Ordering** | ✅ Per-partition | ✅ Per-stream | ⚠️ Per-queue |
| **Consumer Groups** | ✅ Built-in | ✅ Built-in | ✅ Built-in |
| **Event Replay** | ✅ Yes | ✅ Limited | ❌ No |
| **Dead Letter Queues** | ⚠️ Manual | ❌ No | ✅ Built-in |
| **Complex Routing** | ⚠️ Topic-based | ❌ Simple | ✅ Advanced |
| **Schema Evolution** | ✅ Good | ⚠️ Manual | ⚠️ Manual |
| **Transactions** | ✅ Yes | ⚠️ Limited | ✅ Yes |

## Use Case Scenarios

### Scenario 1: Real-Time DSPy Monitoring Dashboard

**Requirements:**
- Live metrics from DSPy modules
- <100ms latency for UI updates
- 10K events/sec
- Simple consumer logic

**Best Choice: Redis**
```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="dspy_live_metrics",
    max_batch_size=50,      # Small batches for low latency
    flush_interval=0.05     # 50ms flush
)
```

**Why Redis?**
- Sub-millisecond event processing
- Simple consumer groups for scaling
- Can double as DSPy result cache
- Minimal operational overhead

### Scenario 2: High-Volume DSPy Analytics Pipeline

**Requirements:**
- 500K+ DSPy events/sec
- 6 months data retention
- Multiple analytics teams
- Event replay for debugging

**Best Choice: Kafka**
```python
from streamll.sinks import KafkaSink

kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="dspy_analytics",
    batch_size=500,         # Large batches for throughput
    compression_type="lz4", # Fast compression
    partitioner_strategy="hash"  # Distribute by execution_id
)
```

**Why Kafka?**
- Handles extreme throughput
- Long-term retention with compaction
- Event replay capabilities
- Horizontal scaling

### Scenario 3: Enterprise DSPy Integration

**Requirements:**
- Route DSPy events by severity/module
- Dead letter queue for failures  
- AMQP protocol requirement
- Complex event filtering

**Best Choice: RabbitMQ**
```python
from streamll.sinks.rabbitmq import RabbitMQSink

rabbitmq_sink = RabbitMQSink(
    amqp_url="amqp://rabbitmq:5672/",
    exchange="dspy_enterprise",
    routing_key="dspy.{module_name}.{event_type}",
    dead_letter_exchange="dspy_failed",
    publisher_confirms=True
)
```

**Why RabbitMQ?**
- Advanced routing patterns
- Built-in dead letter queues
- Enterprise protocol support
- Guaranteed delivery

### Scenario 4: Development & Testing

**Requirements:**
- Simple setup
- Easy debugging
- No persistence needed
- Local development

**Best Choice: Redis**
```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="dspy_dev_events",
    buffer_size=1000,       # Small buffer
    max_stream_length=10000 # Auto-cleanup
)
```

**Why Redis?**
- Single Docker container setup
- Visual inspection with Redis CLI
- No complex configuration
- Fast iteration

## Migration Paths

### From Redis to Kafka (Scaling Up)

**When to migrate:**
- Events exceed 50K/sec consistently  
- Need long-term retention (>1 week)
- Multiple teams need event replay
- Running out of Redis memory

**Migration strategy:**
```python
# Phase 1: Dual-write to both sinks
redis_sink = RedisSink(url="redis://localhost:6379", stream_key="dspy_events")
kafka_sink = KafkaSink(bootstrap_servers="kafka:9092", topic="dspy_events")

streamll.configure(sinks=[redis_sink, kafka_sink])  # Dual-write

# Phase 2: Switch consumers to Kafka
# Phase 3: Remove Redis sink
```

### From RabbitMQ to Kafka (Performance)

**When to migrate:**
- Throughput requirements exceed 20K/sec
- Need event replay capabilities
- Routing logic can be simplified
- Long-term data analytics needs

**Migration strategy:**
```python
# Use topic naming to replicate routing
# RabbitMQ: routing_key="dspy.{module_name}.{event_type}"
# Kafka: topic="dspy_{module_name}" or use message headers
```

### From Kafka to Redis (Simplification)

**When to migrate:**
- Operational complexity too high
- Don't need long-term retention
- Throughput under 50K/sec
- Want real-time analytics

**Migration strategy:**
```python
# Use Redis Streams for similar semantics
# Kafka partitions → Redis stream keys
# Kafka consumer groups → Redis consumer groups
```

## Cost Analysis

### Infrastructure Costs (Monthly, 10K events/sec)

| Sink | Self-Hosted | Managed Service | Notes |
|------|-------------|-----------------|-------|
| **Redis** | $50-100 | $200-400 | ElastiCache, Azure Cache |
| **RabbitMQ** | $100-200 | $300-600 | Amazon MQ, CloudAMQP |
| **Kafka** | $200-400 | $500-1000 | MSK, Confluent Cloud |

### Operational Costs

| Aspect | Redis | RabbitMQ | Kafka |
|--------|-------|----------|-------|
| **Setup Time** | 1 day | 3 days | 1 week |
| **Maintenance** | Low | Medium | High |
| **Expertise Required** | Basic | Intermediate | Advanced |
| **Monitoring Tools** | Simple | Moderate | Complex |

## Cloud Provider Compatibility

### AWS
- **Redis**: ElastiCache (excellent)
- **RabbitMQ**: Amazon MQ (good)
- **Kafka**: MSK (excellent)

### Azure  
- **Redis**: Azure Cache (excellent)
- **RabbitMQ**: Service Bus AMQP (good)
- **Kafka**: Event Hubs (good)

### Google Cloud
- **Redis**: Memorystore (excellent)  
- **RabbitMQ**: Pub/Sub AMQP bridge (limited)
- **Kafka**: Not native (use Confluent)

## Performance Tuning Quick Reference

### Redis Optimization
```python
RedisSink(
    # High throughput
    max_batch_size=500,
    flush_interval=0.1,
    
    # Low latency  
    max_batch_size=1,
    flush_interval=0.01
)
```

### Kafka Optimization
```python
KafkaSink(
    # High throughput
    batch_size=500,
    compression_type="lz4",
    acks="1",
    
    # High durability
    batch_size=50,
    acks="all",
    enable_idempotence=True
)
```

### RabbitMQ Optimization
```python
RabbitMQSink(
    # High throughput
    batch_size=200,
    publisher_confirms=False,
    use_streams=True,
    
    # High reliability
    batch_size=1,
    publisher_confirms=True,
    durable=True
)
```

## Decision Framework

### Step 1: Define Requirements
- [ ] Expected event volume (events/sec)
- [ ] Latency requirements (ms)
- [ ] Retention period (hours/days/months)
- [ ] Number of consumer applications
- [ ] Operational complexity tolerance
- [ ] Budget constraints

### Step 2: Apply Decision Tree

```
Event Volume > 100K/sec? 
├─ Yes → Kafka
└─ No ↓

Need real-time (<1ms)?
├─ Yes → Redis  
└─ No ↓

Need complex routing?
├─ Yes → RabbitMQ
└─ No → Redis (simplest)
```

### Step 3: Validate Choice

Run benchmarks with your actual DSPy workload:

```python
# Benchmark script template
import time
from streamll.models import StreamllEvent

def benchmark_sink(sink, num_events=10000):
    events = [
        StreamllEvent(
            execution_id=f"bench-{i}",
            event_type="benchmark",
            data={"index": i}
        ) for i in range(num_events)
    ]
    
    sink.start()
    start_time = time.time()
    
    for event in events:
        sink.handle_event(event)
    
    sink.flush()
    duration = time.time() - start_time
    throughput = num_events / duration
    
    print(f"{sink.__class__.__name__}: {throughput:.1f} events/sec")
    sink.stop()
```

## Summary

**Choose Redis if:** You need real-time analytics, simple setup, or already use Redis for caching

**Choose Kafka if:** You need high throughput, long retention, event replay, or complex analytics

**Choose RabbitMQ if:** You need complex routing, enterprise integration, or guaranteed delivery with DLQ

**When in doubt:** Start with Redis for simplicity, then migrate to Kafka when you outgrow it.