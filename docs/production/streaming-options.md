# StreamLL Streaming Options Guide

Choose the right streaming backend for your use case. StreamLL provides three built-in sink options, each optimized for different scenarios.

## Quick Comparison

| Feature | TerminalSink | RedisSink | RabbitMQSink |
|---------|--------------|-----------|--------------|
| **Use Case** | Development & debugging | Real-time dashboards | Enterprise workflows |
| **Performance** | Instant | High-throughput | Durable messaging |
| **Persistence** | None | Memory/Disk | Durable queues |
| **Routing** | None | Streams/Keys | Exchange routing |
| **Clustering** | No | Redis Cluster | RabbitMQ cluster |
| **Setup Complexity** | Zero | Minimal | Moderate |
| **Dependencies** | None | Redis server | RabbitMQ server |

## 1. TerminalSink - Development & Debugging ✨

**Perfect for**: Local development, debugging, demos

```python
import streamll
from streamll.sinks import TerminalSink

# Beautiful real-time console output
streamll.configure(sinks=[TerminalSink()])

@streamll.instrument
class MyModule(dspy.Module):
    def forward(self, question):
        return self.llm(question)

# Output:
# [16:31:42.156] ▶ llm_call (a1b2c3d4)
# [16:31:43.156] • llm_call (a1b2c3d4) 'The answer is'
# [16:31:43.298] • llm_call (a1b2c3d4) ' 42'
# [16:31:46.782] ■ llm_call (a1b2c3d4) {"total_tokens": 287}
```

**Features:**
- Zero setup required
- Beautiful colored output with emoji indicators
- Real-time token streaming display
- Execution time and performance metrics
- Perfect for development workflows

## 2. RedisSink - Real-time Dashboards 🚀

**Perfect for**: Production monitoring, real-time analytics, microservices

```python
import streamll
from streamll.sinks import RedisSink

# High-performance streaming to Redis
redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="streamll_events",
    circuit_breaker=True,
    failure_threshold=3,
    recovery_timeout=10.0
)

streamll.configure(sinks=[redis_sink])
```

**Architecture:**
```
DSPy App → StreamLL → Redis Streams → Dashboard
                   ↗ Analytics Service
                   ↗ Monitoring Service
```

**Use Cases:**
- **Real-time dashboards**: Grafana, custom web UIs
- **Stream processing**: Apache Kafka, AWS Kinesis integration
- **Microservices**: Event-driven architecture
- **Analytics**: Token usage, performance monitoring

**Redis Consumer Example:**

```python
import redis

r = redis.Redis()

# Read events in real-time
while True:
    events = r.xread({'streamll_events': '$'}, block=1000)
    for stream, msgs in events:
        for msg_id, fields in msgs:
            event = json.loads(fields[b'event'])
            print(f"Event: {event['event_type']} - {event['operation']}")
```

## 3. RabbitMQSink - Enterprise Workflows 🏢

**Perfect for**: Enterprise systems, workflow automation, audit trails

```python
import streamll
from streamll.sinks import RabbitMQSink

# Enterprise message queuing
rabbitmq_sink = RabbitMQSink(
    amqp_url="amqp://user:pass@rabbitmq.company.com:5672/",
    exchange="ai_events",
    routing_key="dspy.{operation}.{event_type}",
    durable=True,
    circuit_breaker=True
)

streamll.configure(sinks=[rabbitmq_sink])
```

**Architecture:**
```
DSPy App → StreamLL → RabbitMQ Exchange → Multiple Queues
                                       ↗ Audit Service
                                       ↗ Alerting Service  
                                       ↗ Data Warehouse
                                       ↗ Compliance System
```

**Advanced Routing:**

```python
# Route different events to different queues
RabbitMQSink(
    exchange="ai_events",
    routing_key="ai.{module_name}.{event_type}",
    # Routes to:
    # ai.rag_pipeline.start → audit_queue
    # ai.rag_pipeline.token → monitoring_queue
    # ai.rag_pipeline.error → alerts_queue
)
```

**Use Cases:**
- **Audit trails**: Permanent record of all AI operations
- **Compliance**: SOX, GDPR, financial regulations
- **Workflow automation**: Trigger downstream processes
- **Error handling**: Dead letter queues, retry logic
- **Multi-tenant**: Route events by customer/department

## Multi-Sink Configuration

Combine sinks for different environments:

```python
import streamll
from streamll.sinks import TerminalSink, RedisSink, RabbitMQSink

# Development: Terminal only
if os.getenv("ENV") == "development":
    sinks = [TerminalSink()]

# Staging: Terminal + Redis  
elif os.getenv("ENV") == "staging":
    sinks = [
        TerminalSink(),
        RedisSink(url="redis://staging-redis:6379")
    ]

# Production: Redis + RabbitMQ
else:
    sinks = [
        RedisSink(
            url="redis://prod-redis-cluster:6379",
            stream_key="prod_ai_events",
            circuit_breaker=True
        ),
        RabbitMQSink(
            amqp_url="amqp://prod-rabbit-cluster:5672/",
            exchange="production_ai",
            routing_key="ai.{module_name}.{operation}",
            durable=True
        )
    ]

streamll.configure(sinks=sinks)
```

## Installation Commands

```bash
# Development only
pip install streamll

# With Redis support  
pip install streamll[redis]

# With RabbitMQ support
pip install streamll[rabbitmq]

# Everything
pip install streamll[all]
```

## Performance Characteristics

### TerminalSink
- **Latency**: <1ms (synchronous)
- **Throughput**: ~10K events/sec
- **Memory**: Minimal
- **Bottleneck**: Terminal I/O

### RedisSink  
- **Latency**: 1-5ms (async buffered)
- **Throughput**: ~100K events/sec
- **Memory**: Configurable buffer
- **Bottleneck**: Network to Redis

### RabbitMQSink
- **Latency**: 2-10ms (async durable)
- **Throughput**: ~50K events/sec  
- **Memory**: Queue-based buffering
- **Bottleneck**: AMQP protocol overhead

## Circuit Breaker Pattern

Both Redis and RabbitMQ sinks include circuit breakers:

```python
# Circuit breaker configuration
sink = RedisSink(
    circuit_breaker=True,
    failure_threshold=3,      # Open after 3 failures
    recovery_timeout=30.0,    # Try again after 30s
)

# Behavior:
# 1. Normal operation: Events flow normally
# 2. Failures detected: Count failures
# 3. Threshold reached: Circuit opens, events dropped
# 4. Recovery time: Circuit attempts to close
# 5. Success: Circuit closes, normal operation resumes
```

## Monitoring Your Sinks

Check sink health in your application:

```python
# Check sink status
for sink in streamll_sinks:
    print(f"{sink.__class__.__name__}: running={sink.is_running}")
    
    # Redis-specific metrics
    if hasattr(sink, 'failures'):
        print(f"  Failures: {sink.failures}")
        print(f"  Circuit open: {sink.circuit_open}")
    
    # RabbitMQ-specific metrics  
    if hasattr(sink, 'connection'):
        print(f"  Connected: {sink.connection and not sink.connection.is_closed}")
```

## Best Practices

### Development
```python
# Simple terminal output
streamll.configure(sinks=[TerminalSink()])
```

### Staging  
```python
# Terminal + Redis for testing integrations
streamll.configure(sinks=[
    TerminalSink(),
    RedisSink(url=os.getenv("REDIS_URL"))
])
```

### Production
```python
# Redis for real-time + RabbitMQ for durability
streamll.configure(sinks=[
    RedisSink(
        url=os.getenv("REDIS_CLUSTER_URL"),
        circuit_breaker=True,
        failure_threshold=5,
    ),
    RabbitMQSink(
        amqp_url=os.getenv("RABBITMQ_CLUSTER_URL"), 
        exchange="production_ai_events",
        routing_key="ai.{module_name}.{event_type}",
        durable=True,
        circuit_breaker=True,
    )
])
```

Choose the right combination for your architecture! 🎯
