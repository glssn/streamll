# Production Redis Sink

Deploy StreamLL with Redis Streams for production-grade DSPy observability, real-time monitoring, and analytics.

## Why Choose Redis for DSPy Observability?

Redis excels for DSPy applications when you need:

**✅ Real-Time Analytics**: Sub-millisecond event processing for live dashboards  
**✅ Caching + Observability**: Single Redis instance for both DSPy caching and event streaming  
**✅ Simple Consumer Groups**: Built-in horizontal scaling without complex infrastructure  
**✅ Time-Series Queries**: Fast range queries on DSPy execution timelines  
**✅ Memory Efficiency**: Compact storage for high-frequency DSPy events  

**❌ Choose Kafka Instead If**: You need >100K events/sec or long-term (months) retention  
**❌ Choose RabbitMQ Instead If**: You need complex routing or traditional messaging patterns  

## Overview

The RedisSink provides enterprise-ready event streaming with:
- **Circuit breaker** prevents cascade failures  
- **Local buffering** during Redis outages
- **Automatic recovery** with exponential backoff
- **Consumer groups** for horizontal scaling
- **Event persistence** for historical analysis

## Quick Setup

### 1. Start Redis

```bash
# Using Docker (recommended)
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine redis-server --appendonly yes

# Or using Docker Compose
cat > docker-compose.yml << EOF
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
volumes:
  redis_data:
EOF

docker-compose up -d
```

### 2. Configure StreamLL

```python
import streamll
from streamll.sinks import RedisSink

# Basic production configuration
@streamll.instrument(sinks=[
    RedisSink(
        url="redis://localhost:6379",
        stream_key="ml_events"
    )
])
class ProductionModule(dspy.Module):
    pass
```

### 3. Verify Events

```python
import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
entries = r.xread({"ml_events": "0"})

for stream_name, stream_entries in entries:
    print(f"Stream: {stream_name}, Events: {len(stream_entries)}")
```

## Advanced Configuration

### Production-Grade Setup

```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://prod-redis:6379",
    stream_key="dspy_production_events",

    # Resilience settings
    buffer_size=50000,           # Buffer 50k events during outages
    circuit_breaker=True,        # Enable circuit breaker
    failure_threshold=5,         # Open after 5 consecutive failures  
    recovery_timeout=60.0,       # Try recovery every 60 seconds

    # Performance settings
    max_batch_size=500,          # Batch up to 500 events
    flush_interval=1.0,          # Flush every 1 second

    # Stream management
    max_stream_length=1000000,   # Keep last 1M events
    approximate_trimming=True,   # Use MAXLEN ~ for performance

    # Buffer overflow strategy
    buffer_overflow_strategy="drop_oldest"  # or "drop_newest", "raise_error"
)

@streamll.instrument(sinks=[redis_sink])
class ProductionRAG(dspy.Module):
    pass
```

### Environment Variables

```bash
# Redis connection
export REDIS_URL="redis://prod-redis:6379/0"
export REDIS_PASSWORD="your-secure-password"

# StreamLL configuration
export STREAMLL_STREAM_KEY="ml_events_prod"
export STREAMLL_BUFFER_SIZE="100000"
export STREAMLL_CIRCUIT_BREAKER="true"
```

```python
import os
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url=os.getenv("REDIS_URL"),
    stream_key=os.getenv("STREAMLL_STREAM_KEY", "ml_events"),
    buffer_size=int(os.getenv("STREAMLL_BUFFER_SIZE", "10000")),
    circuit_breaker=os.getenv("STREAMLL_CIRCUIT_BREAKER", "true").lower() == "true"
)
```

## Consumer Groups

Scale event processing with Redis consumer groups:

### 1. Configure Consumer Group

```python
from streamll.sinks import RedisSink

# Producer (your DSPy application)
redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="ml_events",
    consumer_group="ml_processors",  # Create consumer group
    consumer_name="producer_app"
)
```

### 2. Create Consumer Application

```python
import redis
import json
import time

class StreamLLConsumer:
    def __init__(self, redis_url, stream_key, consumer_group, consumer_name):
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.stream_key = stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        
        # Create consumer group if it doesn't exist
        try:
            self.redis.xgroup_create(
                stream_key, 
                consumer_group, 
                id="0", 
                mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
    
    def consume_events(self):
        """Consume events from Redis stream."""
        while True:
            try:
                # Read new events
                events = self.redis.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_key: ">"},
                    count=100,
                    block=1000  # Block for 1 second
                )
                
                for stream_name, stream_events in events:
                    for event_id, fields in stream_events:
                        self.process_event(event_id, fields)
                        
                        # Acknowledge processing
                        self.redis.xack(
                            self.stream_key,
                            self.consumer_group,
                            event_id
                        )
                        
            except Exception as e:
                print(f"Consumer error: {e}")
                time.sleep(5)
    
    def process_event(self, event_id, fields):
        """Process a single StreamLL event."""
        event = json.loads(fields["event"])
        
        # Handle different event types
        if event["event_type"] == "llm_call":
            self.handle_llm_call(event)
        elif event["event_type"] == "error":
            self.handle_error(event)
        elif event["event_type"] == "token":
            self.handle_token(event)
    
    def handle_llm_call(self, event):
        """Handle LLM call events."""
        print(f"LLM Call: {event['data'].get('model', 'unknown')}")
    
    def handle_error(self, event):
        """Handle error events."""
        print(f"Error: {event['data'].get('error_type')}")
        # Send alert, log to monitoring system, etc.
    
    def handle_token(self, event):
        """Handle token streaming events."""
        token = event['data'].get('token', '')
        # Stream to WebSocket, update UI, etc.

# Run consumer
consumer = StreamLLConsumer(
    redis_url="redis://localhost:6379",
    stream_key="ml_events",
    consumer_group="analytics_team",
    consumer_name="analytics_worker_1"
)

consumer.consume_events()
```

### 3. Multiple Consumers

Scale horizontally with multiple consumer instances:

```python
# Consumer 1: Real-time analytics
consumer_analytics = StreamLLConsumer(
    redis_url="redis://localhost:6379",
    stream_key="ml_events", 
    consumer_group="analytics",
    consumer_name="analytics_worker_1"
)

# Consumer 2: Alerting system
consumer_alerts = StreamLLConsumer(
    redis_url="redis://localhost:6379",
    stream_key="ml_events",
    consumer_group="alerts", 
    consumer_name="alert_worker_1"
)

# Consumer 3: Data warehouse sync
consumer_warehouse = StreamLLConsumer(
    redis_url="redis://localhost:6379",
    stream_key="ml_events",
    consumer_group="warehouse",
    consumer_name="warehouse_sync_1"
)
```

## Cloud Provider Integration

### AWS ElastiCache for Redis

#### Cluster Mode Configuration
```python
from streamll.sinks import RedisSink

# ElastiCache cluster endpoint
redis_sink = RedisSink(
    url="redis://my-cluster.abc123.cache.amazonaws.com:6379",
    stream_key="dspy_production_events",
    
    # ElastiCache optimizations
    buffer_size=25000,          # ElastiCache handles high throughput
    max_batch_size=200,         # Larger batches for cluster
    circuit_breaker=True,
    
    # VPC security
    ssl=True,                   # Enable TLS in transit
    ssl_cert_reqs=None         # AWS manages certificates
)
```

#### ElastiCache Serverless Configuration
```python
# ElastiCache Serverless (Redis 7.0+)
redis_sink = RedisSink(
    url="redis://serverless-cluster.abc123.serverless.use1.cache.amazonaws.com:6379",
    stream_key="dspy_events",
    
    # Serverless considerations
    max_stream_length=100000,    # Serverless has memory limits
    approximate_trimming=True,   # Reduce memory overhead
    buffer_size=5000,           # Smaller buffer for serverless
    
    # Auth Token (IAM authentication)
    auth_token=os.getenv("ELASTICACHE_AUTH_TOKEN")
)
```

#### Environment Variables for AWS
```bash
# ElastiCache connection details
export REDIS_CLUSTER_ENDPOINT="my-cluster.abc123.cache.amazonaws.com:6379"
export REDIS_AUTH_TOKEN="your-auth-token"  # If auth enabled
export AWS_DEFAULT_REGION="us-east-1"

# StreamLL configuration  
export STREAMLL_STREAM_KEY="dspy_prod_events"
export STREAMLL_BUFFER_SIZE="25000"
```

### Azure Cache for Redis

#### Standard Tier Configuration  
```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://my-cache.redis.cache.windows.net:6380",
    stream_key="dspy_events",
    
    # Azure Cache configuration
    ssl=True,                   # SSL required for Azure Cache
    ssl_cert_reqs="required",   # Verify certificates
    password=os.getenv("AZURE_REDIS_PASSWORD"),
    
    # Azure-optimized settings
    buffer_size=20000,
    max_batch_size=150,
    circuit_breaker=True
)
```

#### Premium Tier with VNet
```python
# Premium tier with VNet injection
redis_sink = RedisSink(
    url="redis://10.0.1.4:6379",  # Private VNet IP
    stream_key="dspy_production_events",
    
    # No SSL needed within VNet
    ssl=False,
    password=os.getenv("AZURE_REDIS_PASSWORD"),
    
    # Premium tier optimizations
    buffer_size=50000,          # Higher memory limits
    max_batch_size=500,         # Larger batches
    flush_interval=0.5          # Batch more aggressively
)
```

### Google Cloud Memorystore for Redis

#### Standard Instance Configuration
```python
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    url="redis://10.0.0.3:6379",  # Private GCP IP
    stream_key="dspy_events",
    
    # Memorystore optimizations
    buffer_size=30000,
    max_batch_size=250,
    
    # No authentication needed for basic tier
    ssl=False,  # TLS optional in private VPC
    
    # GCP-specific settings
    circuit_breaker=True,
    failure_threshold=3,        # Lower threshold for GCP networking
    recovery_timeout=15.0       # Faster recovery testing
)
```

#### High Availability Configuration
```python
# HA instance with failover
redis_sink = RedisSink(
    url="redis://10.0.0.3:6379",
    stream_key="dspy_ha_events",
    
    # HA optimizations
    buffer_size=40000,          # Handle failover periods
    circuit_breaker=True,
    failure_threshold=5,        # More tolerance for HA failover
    recovery_timeout=30.0,      # Allow time for failover
    
    # Connection pooling for HA
    max_connections=20
)
```

## Circuit Breaker Pattern

Understand how StreamLL's circuit breaker protects your application:

### Circuit States

```python
from streamll.sinks.redis import CircuitBreaker

# Circuit breaker configuration
breaker = CircuitBreaker(
    failure_threshold=3,    # Open after 3 failures
    recovery_timeout=30.0   # Try recovery every 30 seconds
)

# Circuit breaker states:
# 1. CLOSED: Normal operation, requests pass through
# 2. OPEN: Failures detected, requests are blocked/buffered  
# 3. HALF-OPEN: Testing if service recovered
```

### Monitoring Circuit Breaker

```python
import streamll
from streamll.sinks import RedisSink

# Create sink with circuit breaker monitoring
redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="ml_events",
    circuit_breaker=True,
    failure_threshold=3,
    recovery_timeout=30.0
)

# Monitor circuit breaker state
def check_circuit_state():
    if hasattr(redis_sink, '_circuit_breaker'):
        breaker = redis_sink._circuit_breaker
        print(f"Circuit breaker open: {breaker.is_open}")
        print(f"Failure count: {breaker.failure_count}")
        print(f"Last failure: {breaker.last_failure_time}")

# Check periodically
import threading
import time

def monitor_circuit():
    while True:
        check_circuit_state()
        time.sleep(10)

monitor_thread = threading.Thread(target=monitor_circuit)
monitor_thread.daemon = True
monitor_thread.start()
```

## Event Schema & Analytics

### Event Structure

Every StreamLL event in Redis follows this schema:

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "event_type": "llm_call", 
  "timestamp": "2024-01-15T16:30:45.123456Z",
  "execution_id": "exec_abc123",
  "operation": "answer_generation",
  "data": {
    "model": "gemini/gemini-2.0-flash",
    "tokens_used": 287,
    "cost_usd": 0.0023,
    "response_time_ms": 1234
  },
  "tags": {
    "environment": "production",
    "user_id": "user_123"
  }
}
```

### Analytics Queries

```python
import redis
import json
from datetime import datetime, timedelta

def analyze_llm_usage(hours=24):
    """Analyze LLM usage over the last N hours."""
    
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    start_ts = int(start_time.timestamp() * 1000)
    
    # Read events from time range
    entries = r.xrange("ml_events", min=start_ts)
    
    stats = {
        "total_calls": 0,
        "total_tokens": 0,
        "total_cost": 0.0,
        "avg_response_time": 0,
        "models_used": {},
        "errors": 0
    }
    
    response_times = []
    
    for entry_id, fields in entries:
        event = json.loads(fields["event"])
        
        if event["event_type"] == "llm_call":
            stats["total_calls"] += 1
            
            data = event.get("data", {})
            stats["total_tokens"] += data.get("tokens_used", 0)
            stats["total_cost"] += data.get("cost_usd", 0)
            
            if "response_time_ms" in data:
                response_times.append(data["response_time_ms"])
            
            model = data.get("model", "unknown")
            stats["models_used"][model] = stats["models_used"].get(model, 0) + 1
            
        elif event["event_type"] == "error":
            stats["errors"] += 1
    
    if response_times:
        stats["avg_response_time"] = sum(response_times) / len(response_times)
    
    return stats

# Run analytics
stats = analyze_llm_usage(hours=24)
print(f"Total LLM calls: {stats['total_calls']}")
print(f"Total tokens: {stats['total_tokens']:,}")
print(f"Total cost: ${stats['total_cost']:.4f}")
print(f"Average response time: {stats['avg_response_time']:.0f}ms")
print(f"Error rate: {stats['errors']/stats['total_calls']*100:.2f}%")
```

## High Availability Setup

### Redis Cluster

For high availability, use Redis cluster or sentinel:

```python
import redis.sentinel

# Redis Sentinel setup
sentinels = [
    ('sentinel1', 26379),
    ('sentinel2', 26379), 
    ('sentinel3', 26379)
]

sentinel = redis.sentinel.Sentinel(sentinels)

# Discover Redis master
redis_master = sentinel.master_for(
    'mymaster',
    socket_timeout=0.1,
    password='your-password'
)

# Use with StreamLL
from streamll.sinks import RedisSink

redis_sink = RedisSink(
    client=redis_master,  # Use pre-configured client
    stream_key="ml_events_ha"
)
```

### Load Balancing

Distribute events across multiple Redis instances:

```python
import hashlib
from streamll.sinks import RedisSink

class ShardedRedisSink:
    def __init__(self, redis_urls, stream_key_prefix="ml_events"):
        self.sinks = []
        for i, url in enumerate(redis_urls):
            sink = RedisSink(
                url=url,
                stream_key=f"{stream_key_prefix}_shard_{i}"
            )
            self.sinks.append(sink)
    
    def get_sink_for_event(self, event):
        # Shard by execution_id for related events
        execution_id = event.execution_id
        shard = int(hashlib.md5(execution_id.encode()).hexdigest(), 16) % len(self.sinks)
        return self.sinks[shard]

# Use sharded setup
sharded_sink = ShardedRedisSink([
    "redis://redis1:6379",
    "redis://redis2:6379", 
    "redis://redis3:6379"
])
```

## Monitoring & Alerting

### Redis Metrics

Monitor Redis health for StreamLL events:

```bash
# Redis CLI monitoring
redis-cli info replication
redis-cli info memory
redis-cli xinfo stream ml_events

# Check stream length
redis-cli xlen ml_events

# Check consumer group status
redis-cli xinfo groups ml_events
```

### StreamLL Metrics

Monitor StreamLL-specific metrics:

```python
import redis
import json

def streamll_health_check():
    """Check StreamLL Redis sink health."""

    r = redis.Redis(host='localhost', port=6379, decode_responses=True)

    metrics = {}

    # Stream length
    metrics["stream_length"] = r.xlen("ml_events")

    # Recent event rate
    now = int(time.time() * 1000)
    minute_ago = now - 60000
    recent_events = r.xrange("ml_events", min=minute_ago, max=now)
    metrics["events_per_minute"] = len(recent_events)

    # Consumer group lag
    try:
        groups = r.xinfo_groups("ml_events")
        metrics["consumer_groups"] = len(groups)
        metrics["total_lag"] = sum(group["lag"] for group in groups)
    except:
        metrics["consumer_groups"] = 0
        metrics["total_lag"] = 0

    # Error rate
    error_events = [
        event for event_id, event_data in recent_events
        for event in [json.loads(event_data["event"])]
        if event["event_type"] == "error"
    ]
    metrics["error_rate"] = len(error_events) / max(len(recent_events), 1)

    return metrics

# Health check alerts
def alert_if_unhealthy():
    metrics = streamll_health_check()

    if metrics["events_per_minute"] == 0:
        print("ALERT: No recent events - StreamLL may be down")

    if metrics["total_lag"] > 1000:
        print(f"ALERT: High consumer lag: {metrics['total_lag']}")

    if metrics["error_rate"] > 0.05:
        print(f"ALERT: High error rate: {metrics['error_rate']*100:.1f}%")
```

## Troubleshooting

### Common Issues

**Events not appearing in Redis:**
```python
# Check Redis connection
import redis
r = redis.Redis(host='localhost', port=6379)
r.ping()  # Should return True

# Check StreamLL configuration
print(redis_sink.is_running)
print(len(redis_sink._local_buffer))  # Should be 0 if flushing properly
```

**Circuit breaker stuck open:**
```python
# Force circuit breaker reset
if hasattr(redis_sink, '_circuit_breaker'):
    redis_sink._circuit_breaker.record_success()
    print("Circuit breaker reset")
```

**High memory usage:**
```python
# Check buffer size
print(f"Buffer size: {len(redis_sink._local_buffer)}")

# Reduce buffer size
redis_sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="ml_events",
    buffer_size=1000  # Smaller buffer
)
```

### Debug Mode

Enable verbose logging:

```python
import logging

# Enable StreamLL debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("streamll.sinks.redis")
logger.setLevel(logging.DEBUG)

# Run your application with debug output
```

## Best Practices

1. **Use consumer groups** for horizontal scaling
2. **Monitor circuit breaker state** in production
3. **Set appropriate buffer sizes** based on your event volume
4. **Enable stream trimming** to prevent unbounded growth
5. **Use Redis persistence** (AOF) for critical events
6. **Monitor Redis memory usage** and set limits
7. **Implement proper error handling** in consumers
8. **Use connection pooling** for high-throughput scenarios

## Next Steps

- **[Monitoring Guide](monitoring.md)** - Set up alerts and dashboards
- **[Performance Tuning](performance.md)** - Optimize for scale
- **[Security Guide](security.md)** - Secure your Redis deployment
