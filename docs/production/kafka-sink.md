# Kafka Sink Production Guide

The Kafka sink provides high-throughput, distributed event streaming for DSPy observability using the Apache Kafka protocol. It's designed following the Diamond Development Process for production resilience.

## Why Choose Kafka for DSPy Observability?

Kafka excels for DSPy applications when you need:

**✅ Event Streaming & Replay**: Replay DSPy executions from Kafka events for debugging  
**✅ Multi-Consumer Analytics**: Multiple teams consuming same DSPy event stream  
**✅ High-Volume AI Workloads**: >10K DSPy forward() calls per second  
**✅ Long-Term Data Retention**: Keep DSPy execution history for weeks/months  
**✅ Integration with Data Pipeline**: Feed DSPy events into data warehouses/analytics  

**❌ Choose Redis Instead If**: You need real-time caching or simple pub/sub  
**❌ Choose RabbitMQ Instead If**: You need task queues or complex routing logic  

## Overview

The KafkaSink publishes StreamllEvent instances to Kafka topics with:
- **Data Integrity**: At-least-once delivery with idempotent producers
- **Reliability**: Circuit breaker pattern and automatic reconnection
- **Architecture**: Consistent with Redis/RabbitMQ sink patterns
- **Performance**: Batching, compression, and partition strategies
- **DSPy Schema**: Structured event format for AI/LLM observability

## Installation

```bash
# Install with Kafka support
pip install streamll[kafka]

# Or install all sinks
pip install streamll[all]
```

## Basic Usage

```python
import streamll
from streamll.sinks import KafkaSink

# Configure Kafka sink
kafka_sink = KafkaSink(
    bootstrap_servers="localhost:9092",
    topic="streamll_events",
    batch_size=100,
    compression_type="gzip"
)

# Use with StreamLL
streamll.configure(sinks=[kafka_sink])
```

## DSPy Integration Patterns

### Pattern 1: DSPy Module Observability

Stream all DSPy module executions to Kafka for analytics:

```python
import dspy
import streamll
from streamll.sinks import KafkaSink

# Configure Kafka for DSPy observability
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="dspy_executions",
    partitioner_strategy="hash"  # Same execution_id → same partition
)

streamll.configure(sinks=[kafka_sink])

# Your DSPy modules automatically stream events
class RAGModule(dspy.Module):
    def __init__(self):
        self.retrieve = dspy.Retrieve(k=5)
        self.generate = dspy.ChainOfThought("context, question -> answer")
    
    def forward(self, question):
        # StreamLL automatically captures:
        # - Module start/end events with module_version
        # - LLM call events with token usage
        # - Error events if any failures occur
        context = self.retrieve(question)
        return self.generate(context=context, question=question)

# All forward() calls generate Kafka events
rag = RAGModule()
answer = rag("What is DSPy?")  # → Events in Kafka topic
```

### Pattern 2: Token-by-Token LLM Streaming

Stream individual tokens for real-time UI updates:

```python
import streamll
from streamll.sinks import KafkaSink

# Separate topic for token streams (high volume)
token_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092", 
    topic="llm_tokens",
    batch_size=1,           # Low latency for real-time
    batch_timeout_ms=10,    # Quick flush
    compression_type="lz4"  # Fast compression
)

streamll.configure(
    sinks=[token_sink],
    event_filter={"token"}  # Only token events
)

# Consumer can build real-time chat UI
async def stream_to_websocket():
    from aiokafka import AIOKafkaConsumer
    
    consumer = AIOKafkaConsumer(
        "llm_tokens",
        bootstrap_servers="kafka:9092"
    )
    await consumer.start()
    
    async for msg in consumer:
        event = json.loads(msg.value)
        if event["event_type"] == "token":
            token = event["data"]["token"]
            await websocket.send(token)  # Real-time to frontend
```

### Pattern 3: DSPy Optimizer Events

Capture DSPy optimization process for analysis:

```python
import dspy
import streamll
from streamll.sinks import KafkaSink

# Track DSPy optimizer performance  
optimizer_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="dspy_optimization",
    compression_type="gzip"  # Optimizer events can be large
)

streamll.configure(sinks=[optimizer_sink])

# DSPy optimizer events automatically captured
teleprompter = dspy.BootstrapFewShot(metric=my_metric)
optimized_module = teleprompter.compile(my_module, trainset=train_data)

# Kafka now contains:
# - Each optimization iteration
# - Metric scores per example
# - Final optimized parameters
```

### Pattern 4: Multi-Environment DSPy Tracking

Route different environments to different Kafka topics:

```python
import os
import streamll
from streamll.sinks import KafkaSink

env = os.getenv("ENVIRONMENT", "dev")

kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic=f"dspy_{env}_events",  # dspy_prod_events, dspy_dev_events
    tags={"environment": env}     # Add environment to all events
)

streamll.configure(sinks=[kafka_sink])

# Events automatically tagged with environment
# Analytics can filter/compare across environments
```

## StreamllEvent Schema for DSPy

Every event in Kafka follows this schema optimized for DSPy observability:

```json
{
  "event_id": "aMjQENZN75kb",
  "execution_id": "exec_abc123",
  "timestamp": "2024-01-15T16:30:45.123456Z",
  
  "module_name": "RAGModule", 
  "method_name": "forward",
  "module_version": "e0f475dd8cfa",  // NEW: AST hash for change detection
  
  "event_type": "start|end|token|error",
  "operation": "module_forward|llm_call|retrieval|optimization",
  
  "data": {
    // Event-specific data
    "model": "gemini/gemini-2.0-flash",
    "tokens_used": 287,
    "cost_usd": 0.0023,
    "inputs": {"question": "What is DSPy?"},
    "outputs": {"answer": "DSPy is..."}
  },
  
  "tags": {
    "environment": "production",
    "user_id": "user_123"
  }
}
```

**Key DSPy-Specific Fields:**
- `module_version`: Detects when module code changes (performance regressions)
- `execution_id`: Groups all events from a single forward() call
- `operation`: Distinguishes DSPy operations (module_forward, llm_call, etc.)
- `data.model`: Tracks which LLM models are being used
- `data.tokens_used`: Essential for cost tracking

## Diamond Approach Configuration

### 1. Data Integrity (Priority 1)

Ensure reliable event delivery with no data loss:

```python
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="production_events",
    
    # Data integrity settings
    acks="all",                    # Wait for all replicas
    enable_idempotence=True,       # Prevent duplicates
    max_in_flight_requests=1,      # Maintain order with retries
)
```

### 2. Reliability (Priority 2)

Handle failures gracefully with circuit breaker:

```python
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="production_events",
    
    # Reliability settings
    circuit_breaker=True,
    failure_threshold=5,           # Open after 5 failures
    recovery_timeout=30.0,         # Try recovery after 30s
    max_retries=3,                 # Retry failed sends
    retry_backoff_ms=100,          # Exponential backoff
    request_timeout_ms=30000,      # 30s timeout
)
```

### 3. Architecture Consistency (Priority 3)

Match patterns from Redis/RabbitMQ sinks:

```python
# Consistent with other sinks
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="streamll_events",
    
    # Same patterns as Redis/RabbitMQ
    batch_size=50,                # Batch like Redis pipelines
    batch_timeout_ms=100,          # Timeout like RabbitMQ
    buffer_size=1000,              # Internal buffer size
)

# Works with same context manager pattern
with kafka_sink:
    # Events are handled
    pass
```

### 4. Performance (Priority 4)

Optimize for high throughput:

```python
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="high_volume_events",
    
    # Performance optimizations
    batch_size=200,               # Large batches
    batch_timeout_ms=50,           # Quick timeout
    compression_type="snappy",     # Fast compression
    partitioner_strategy="hash",   # Smart partitioning
)
```

## Production Configurations

### High Throughput Configuration

```python
# For maximum throughput (>100K events/sec)
kafka_sink = KafkaSink(
    bootstrap_servers="kafka1:9092,kafka2:9092,kafka3:9092",
    topic="high_throughput_events",
    
    # Throughput optimizations
    acks="1",                      # Only leader acknowledgment
    batch_size=500,                # Large batches
    batch_timeout_ms=10,           # Minimal latency
    compression_type="lz4",        # Fast compression
    buffer_size=10000,             # Large buffer
    
    # Still maintain reliability
    circuit_breaker=True,
    failure_threshold=10,
    max_retries=2,
)
```

### High Durability Configuration

```python
# For critical data (financial, compliance)
kafka_sink = KafkaSink(
    bootstrap_servers="kafka1:9092,kafka2:9092,kafka3:9092",
    topic="critical_events",
    
    # Maximum durability
    acks="all",                    # All replicas must confirm
    enable_idempotence=True,       # No duplicates
    max_in_flight_requests=1,      # Strict ordering
    
    # Enhanced reliability
    max_retries=5,
    retry_backoff_ms=200,
    request_timeout_ms=60000,      # 60s timeout
    
    # Moderate performance
    batch_size=50,
    compression_type="gzip",       # Better compression
)
```

### Multi-Datacenter Configuration

```python
# For geo-distributed Kafka clusters
kafka_sink = KafkaSink(
    bootstrap_servers="dc1-kafka:9092,dc2-kafka:9092",
    topic="global_events",
    
    # Multi-DC settings
    acks="all",                    # Cross-DC replication
    compression_type="zstd",       # Best compression for WAN
    batch_size=100,
    batch_timeout_ms=200,          # Allow time for batching
    
    # Handle network issues
    request_timeout_ms=120000,     # 2min for cross-DC
    max_retries=10,
    circuit_breaker=True,
    recovery_timeout=60.0,
)
```

## Partitioning Strategies

### Round-Robin (Default)

```python
# Events distributed evenly across partitions
kafka_sink = KafkaSink(
    bootstrap_servers="localhost:9092",
    topic="events",
    partitioner_strategy="round_robin"  # Default
)
```

### Hash Partitioning

```python
# Events with same execution_id go to same partition
kafka_sink = KafkaSink(
    bootstrap_servers="localhost:9092",
    topic="events",
    partitioner_strategy="hash"  # By execution_id
)
```

### Sticky Partitioning

```python
# Events from same module stick to same partition
kafka_sink = KafkaSink(
    bootstrap_servers="localhost:9092",
    topic="events",
    partitioner_strategy="sticky"  # By module:method
)
```

## Compression Options

```python
# No compression (lowest latency)
compression_type="none"

# GZIP (best compression ratio, higher CPU)
compression_type="gzip"

# Snappy (balanced, good for most cases)
compression_type="snappy"  

# LZ4 (fast compression, low CPU)
compression_type="lz4"

# ZSTD (best compression for bandwidth-limited)
compression_type="zstd"
```

## Message Headers

Kafka messages include headers for routing and filtering:

```python
# Headers automatically added to each message:
{
    "streamll_version": "0.1.0",
    "event_type": "llm_call",
    "operation": "completion",
    "module_name": "my_module",
    "execution_id": "abc123"
}

# Use headers for consumer filtering
```

## Monitoring

### Check Sink Health

```python
# Monitor Kafka sink status
print(f"Running: {kafka_sink.is_running}")
print(f"Failures: {kafka_sink.failures}")

# Circuit breaker status
if kafka_sink._circuit_breaker:
    cb = kafka_sink._circuit_breaker
    print(f"Circuit state: {'OPEN' if cb.is_open else 'CLOSED'}")
    print(f"Failure count: {cb.failure_count}")
```

### Metrics to Monitor

- **Producer Metrics**: Send rate, batch size, compression ratio
- **Circuit Breaker**: Open/close events, failure rate
- **Latency**: Time from event to acknowledgment
- **Throughput**: Events per second

## Using with Redpanda

Redpanda is a Kafka-compatible streaming platform that's easier to deploy:

```python
# Redpanda uses same Kafka protocol
kafka_sink = KafkaSink(
    bootstrap_servers="redpanda:9092",  # Redpanda broker
    topic="streamll_events",
    # All Kafka features work with Redpanda
)
```

### Docker Compose for Testing

```yaml
services:
  redpanda:
    image: redpandadata/redpanda:latest
    ports:
      - "9092:9092"
    command:
      - redpanda
      - start
      - --smp 1
      - --memory 1G
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://localhost:9092
```

## Consumer Example

```python
from aiokafka import AIOKafkaConsumer
import json

async def consume_events():
    consumer = AIOKafkaConsumer(
        "streamll_events",
        bootstrap_servers="localhost:9092",
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    await consumer.start()
    
    try:
        async for msg in consumer:
            event = msg.value
            print(f"Event: {event['event_type']} - {event['operation']}")
            
            # Access headers
            headers = dict(msg.headers) if msg.headers else {}
            print(f"Headers: {headers}")
    finally:
        await consumer.stop()
```

## Error Handling

### Dead Letter Topic

```python
# Send failed events to dead letter topic
class KafkaWithDLQ(KafkaSink):
    def __init__(self, *args, dlq_topic="dead_letter", **kwargs):
        super().__init__(*args, **kwargs)
        self.dlq_topic = dlq_topic
    
    async def _handle_failure(self, event):
        # Send to DLQ
        await self.producer.send(self.dlq_topic, value=event)
        await super()._handle_failure()
```

### Circuit Breaker Events

```python
# Monitor circuit breaker state changes
import logging

logging.getLogger("streamll.sinks.kafka").setLevel(logging.INFO)

# Logs will show:
# INFO: Kafka sink started
# WARNING: Failed to connect to Kafka
# INFO: Circuit breaker opened after 5 failures
# INFO: Circuit breaker attempting recovery
```

## Best Practices

1. **Topic Design**: Use meaningful topic names with versioning
2. **Partition Count**: Start with 3-5 partitions, scale as needed
3. **Replication Factor**: Use 3 for production
4. **Retention**: Set appropriate retention for your use case
5. **Monitoring**: Track lag, throughput, and error rates
6. **Compression**: Use snappy for balanced performance
7. **Batching**: Tune batch_size based on event rate

## Performance Benchmarks

Typical performance with 3-node Kafka cluster:

| Configuration | Throughput | Latency | Use Case |
|--------------|------------|---------|----------|
| High Throughput | 100K+ events/sec | 10-50ms | Analytics |
| Balanced | 50K events/sec | 5-20ms | General |
| High Durability | 20K events/sec | 20-100ms | Critical |

## Cloud Provider Integration

### AWS MSK (Managed Streaming for Apache Kafka)

#### IAM Authentication (Recommended)
```python
from streamll.sinks import KafkaSink

# Using IAM authentication (no passwords in code)
kafka_sink = KafkaSink(
    bootstrap_servers="b-1.mycluster.abc123.c1.kafka.us-east-1.amazonaws.com:9098",
    topic="dspy_production_events",
    
    # AWS MSK IAM configuration
    security_protocol="SASL_SSL",
    sasl_mechanism="AWS_MSK_IAM",
    sasl_oauth_token_provider="aws"  # Uses AWS credentials
)

# Ensure your IAM role has these permissions:
# - kafka-cluster:Connect
# - kafka-cluster:WriteData  
# - kafka-cluster:DescribeCluster
```

#### Environment Setup for MSK
```bash
# Set AWS credentials (use IAM roles in production)
export AWS_DEFAULT_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# MSK-specific environment variables
export MSK_BOOTSTRAP_SERVERS="b-1.mycluster.abc123.c1.kafka.us-east-1.amazonaws.com:9098"
export MSK_TOPIC="dspy_production_events"
```

```python
import os
from streamll.sinks import KafkaSink

kafka_sink = KafkaSink(
    bootstrap_servers=os.getenv("MSK_BOOTSTRAP_SERVERS"),
    topic=os.getenv("MSK_TOPIC"),
    security_protocol="SASL_SSL",
    sasl_mechanism="AWS_MSK_IAM"
)
```

### Confluent Cloud

#### API Key Authentication
```python
from streamll.sinks import KafkaSink

kafka_sink = KafkaSink(
    bootstrap_servers="pkc-abc123.us-east-1.aws.confluent.cloud:9092",
    topic="dspy_events",
    
    # Confluent Cloud authentication
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_username="YOUR_API_KEY",           # Confluent Cloud API Key
    sasl_password="YOUR_API_SECRET",        # Confluent Cloud API Secret
    
    # Performance optimizations for Confluent Cloud
    acks="all",
    compression_type="snappy",
    batch_size=100
)
```

#### Environment Variables for Confluent Cloud
```bash
# Store credentials securely
export CONFLUENT_BOOTSTRAP_SERVERS="pkc-abc123.us-east-1.aws.confluent.cloud:9092"
export CONFLUENT_API_KEY="your-api-key"
export CONFLUENT_API_SECRET="your-api-secret"
export CONFLUENT_TOPIC="dspy_events"
```

```python
import os
from streamll.sinks import KafkaSink

kafka_sink = KafkaSink(
    bootstrap_servers=os.getenv("CONFLUENT_BOOTSTRAP_SERVERS"),
    topic=os.getenv("CONFLUENT_TOPIC"),
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN", 
    sasl_username=os.getenv("CONFLUENT_API_KEY"),
    sasl_password=os.getenv("CONFLUENT_API_SECRET")
)
```

### Azure Event Hubs (Kafka-Compatible)

#### Connection String Authentication
```python
from streamll.sinks import KafkaSink

# Event Hubs connection string format
connection_string = (
    "Endpoint=sb://your-namespace.servicebus.windows.net/;"
    "SharedAccessKeyName=your-policy;"
    "SharedAccessKey=your-key"
)

kafka_sink = KafkaSink(
    bootstrap_servers="your-namespace.servicebus.windows.net:9093",
    topic="dspy-events",  # Event Hub name
    
    # Azure Event Hubs authentication
    security_protocol="SASL_SSL",
    sasl_mechanism="PLAIN",
    sasl_username="$ConnectionString",      # Literal string
    sasl_password=connection_string,        # Full connection string
    
    # Event Hubs specific settings
    client_id="streamll-producer"
)
```

#### Managed Identity Authentication (Recommended for Azure)
```python
from azure.identity import DefaultAzureCredential
from streamll.sinks import KafkaSink

# Uses Azure Managed Identity (no secrets in code)
kafka_sink = KafkaSink(
    bootstrap_servers="your-namespace.servicebus.windows.net:9093",
    topic="dspy-events",
    security_protocol="SASL_SSL",
    sasl_mechanism="OAUTHBEARER",
    sasl_oauth_token_provider="azure",  # Uses DefaultAzureCredential
)
```

### Google Cloud Pub/Sub (Kafka-Compatible via Dataflow)

#### Service Account Authentication
```python
import os
from streamll.sinks import KafkaSink

# Set service account key path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/service-account-key.json"

kafka_sink = KafkaSink(
    bootstrap_servers="your-kafka-cluster.us-central1.gcp.cloud:9092",
    topic="dspy_events",
    
    # GCP authentication handled by service account
    security_protocol="SASL_SSL",
    sasl_mechanism="GSSAPI",  # or OAUTHBEARER for modern setups
    
    # GCP specific optimizations
    compression_type="gzip",
    batch_size=200
)
```

## Circuit Breaker Behavior

### What Happens When Kafka Is Unavailable

The circuit breaker protects your DSPy application from Kafka outages:

```python
kafka_sink = KafkaSink(
    bootstrap_servers="kafka-cluster:9092",
    topic="dspy_events",
    
    # Circuit breaker configuration
    circuit_breaker=True,
    failure_threshold=5,        # Open after 5 failures
    recovery_timeout=30.0,      # Try recovery every 30s
)
```

**Circuit States:**

1. **CLOSED (Normal)**: Events flow to Kafka
2. **OPEN (Failure)**: Events buffered locally, Kafka calls blocked
3. **HALF-OPEN (Testing)**: Single test request to check recovery

**Behavior During Outage:**
```python
# Circuit breaker open - events are buffered locally
rag = RAGModule()
answer = rag("question")  # Still works! Events buffered in memory

# Check circuit state
if kafka_sink._circuit_breaker.is_open:
    print("Kafka unavailable, events buffered locally")
    print(f"Buffered events: {len(kafka_sink._buffer)}")

# When Kafka recovers, circuit closes and buffer flushes
```

**Recovery Process:**
1. Circuit breaker detects Kafka is available
2. Buffered events are sent to Kafka in batch
3. Circuit returns to CLOSED state
4. Normal operation resumes

**Buffer Overflow Strategy:**
```python
kafka_sink = KafkaSink(
    # ...
    buffer_size=10000,                    # Max 10K events in buffer
    buffer_overflow_strategy="drop_oldest"  # or "drop_newest", "raise_error"
)
```

## Practical Consumer Examples

### Python Consumer for DSPy Analytics

```python
from aiokafka import AIOKafkaConsumer
import json
import asyncio

class DSPyAnalyticsConsumer:
    def __init__(self, kafka_servers, topic):
        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="dspy_analytics"
        )
    
    async def consume_dspy_events(self):
        await self.consumer.start()
        try:
            async for message in self.consumer:
                event = message.value
                await self.process_dspy_event(event)
        finally:
            await self.consumer.stop()
    
    async def process_dspy_event(self, event):
        """Process different types of DSPy events."""
        event_type = event["event_type"]
        operation = event.get("operation", "")
        
        if event_type == "start" and operation == "module_forward":
            await self.track_module_execution_start(event)
        elif event_type == "end" and operation == "module_forward":
            await self.track_module_execution_end(event)
        elif event_type == "start" and operation == "llm_call":
            await self.track_llm_call(event)
        elif event_type == "error":
            await self.handle_error_event(event)
    
    async def track_module_execution_start(self, event):
        """Track when DSPy modules start executing."""
        execution_id = event["execution_id"]
        module_name = event["module_name"]
        module_version = event.get("module_version")
        
        print(f"Module {module_name} started (version: {module_version})")
        
        # Store in analytics database
        await self.store_execution_start(execution_id, module_name, module_version)
    
    async def track_llm_call(self, event):
        """Track LLM usage for cost analysis."""
        data = event.get("data", {})
        model = data.get("model", "unknown")
        tokens = data.get("tokens_used", 0)
        cost = data.get("cost_usd", 0)
        
        print(f"LLM call: {model}, tokens: {tokens}, cost: ${cost:.4f}")
        
        # Update cost tracking
        await self.update_cost_metrics(model, tokens, cost)

# Run the consumer
consumer = DSPyAnalyticsConsumer(
    kafka_servers="kafka-cluster:9092",
    topic="dspy_events"
)

asyncio.run(consumer.consume_dspy_events())
```

### Real-Time DSPy Dashboard Consumer

```python
import asyncio
import json
from aiokafka import AIOKafkaConsumer
from collections import defaultdict, deque
from datetime import datetime

class DSPyDashboardConsumer:
    def __init__(self, kafka_servers, topic):
        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id="dspy_dashboard"
        )
        
        # Real-time metrics
        self.active_executions = {}
        self.error_rate = deque(maxlen=100)  # Last 100 events
        self.cost_per_hour = defaultdict(float)
        self.response_times = deque(maxlen=1000)
    
    async def consume_for_dashboard(self):
        await self.consumer.start()
        try:
            async for message in self.consumer:
                event = message.value
                await self.update_dashboard_metrics(event)
                await self.emit_dashboard_update()
        finally:
            await self.consumer.stop()
    
    async def update_dashboard_metrics(self, event):
        """Update real-time dashboard metrics."""
        event_type = event["event_type"]
        execution_id = event["execution_id"]
        timestamp = datetime.fromisoformat(event["timestamp"].replace('Z', '+00:00'))
        
        if event_type == "start":
            self.active_executions[execution_id] = {
                "start_time": timestamp,
                "module_name": event["module_name"]
            }
        
        elif event_type == "end":
            if execution_id in self.active_executions:
                start_time = self.active_executions[execution_id]["start_time"]
                duration = (timestamp - start_time).total_seconds() * 1000
                self.response_times.append(duration)
                del self.active_executions[execution_id]
        
        elif event_type == "error":
            self.error_rate.append(1)
        else:
            self.error_rate.append(0)
        
        # Track costs
        data = event.get("data", {})
        if "cost_usd" in data:
            hour = timestamp.strftime("%Y-%m-%d %H:00")
            self.cost_per_hour[hour] += data["cost_usd"]
    
    async def emit_dashboard_update(self):
        """Emit dashboard update via WebSocket."""
        metrics = {
            "active_executions": len(self.active_executions),
            "error_rate": sum(self.error_rate) / len(self.error_rate) if self.error_rate else 0,
            "avg_response_time": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "current_hour_cost": self.cost_per_hour.get(datetime.now().strftime("%Y-%m-%d %H:00"), 0)
        }
        
        # Send to WebSocket, update database, etc.
        print(f"Dashboard metrics: {metrics}")

# Run dashboard consumer
dashboard = DSPyDashboardConsumer(
    kafka_servers="kafka-cluster:9092", 
    topic="dspy_events"
)

asyncio.run(dashboard.consume_for_dashboard())
```

## Troubleshooting

### Connection Issues

```python
# Test connectivity
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(("localhost", 9092))
if result == 0:
    print("Kafka is accessible")
```

### Performance Issues

1. Check network latency to Kafka brokers
2. Monitor CPU usage (compression overhead)
3. Verify batch settings are optimal
4. Check Kafka broker disk I/O

### Data Loss

1. Verify `acks="all"` for critical data
2. Check replication factor
3. Monitor ISR (in-sync replicas)
4. Enable idempotent producer

## Comparison with Other Sinks

| Feature | Kafka | Redis | RabbitMQ |
|---------|-------|-------|----------|
| Throughput | Highest | High | Medium |
| Durability | Excellent | Good | Excellent |
| Ordering | Per-partition | Stream-based | Queue-based |
| Scaling | Horizontal | Cluster | Cluster |
| Complexity | High | Low | Medium |
| Use Case | Event streaming | Real-time cache | Task queues |