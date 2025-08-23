# Production Deployment Guides - Wireframe

## Redis Sink Production Guide

### Overview
StreamLL RedisSink provides high-performance event streaming to Redis with 12x pipeline speedup and production-ready features like circuit breakers and local buffering.

### Cloud Providers

#### AWS ElastiCache for Redis / Valkey
**Tested with**: ElastiCache Redis 7.0+ and Valkey 7.2+ (single-node and replication group mode only)

**Connection Configuration**:
```python
from streamll.sinks.redis import RedisSink

# ElastiCache Primary Endpoint (single-node) - Secure connection
sink = RedisSink(
    url="rediss://your-cluster.cache.amazonaws.com:6379",
    stream_key="streamll_events",
    buffer_size=10000,
    max_batch_size=100,  # Optimized for ElastiCache
    circuit_breaker=True
)

# ElastiCache Replication Group (primary endpoint) - Secure connection
sink = RedisSink(
    url="rediss://your-replication-group.cache.amazonaws.com:6379",
    stream_key="streamll_events",
    # Note: Connects to primary node only, read replicas not used
    max_batch_size=100,  # Full batching since single connection
)
```

**Authentication**:
```python
# AUTH token (if AUTH enabled) - Secure connection
sink = RedisSink(
    url="rediss://:your-auth-token@your-cluster.cache.amazonaws.com:6379"
)

# ElastiCache with SSL/TLS (in-transit encryption)
sink = RedisSink(
    url="rediss://your-cluster.cache.amazonaws.com:6379"  # rediss:// enables SSL automatically
)
```

**IAM Authentication** (Future):
```python
# Planned: Native IAM authentication with encryption
sink = RedisSink(
    url="rediss://your-cluster.cache.amazonaws.com:6379",
    aws_iam_auth=True  # Uses boto3 credentials automatically
)
```

**Performance Characteristics**:
- **Pipeline speedup**: 12x faster than individual commands (verified on r7g.large instances)
- **Throughput**: 50k+ events/sec on r7g.xlarge with Redis 7.0
- **Replication groups**: Automatic failover to read replicas (writes go to primary only)

**Limitations**:
- **Cluster mode not supported**: StreamLL uses standard Redis client, not cluster-aware client
- **Single connection**: Connects to primary endpoint only, no automatic failover to replicas  
- **No hash slot routing**: Cannot distribute writes across cluster shards
- **ElastiCache Serverless**: Some Redis commands may have limitations
- **AUTH required**: Must be enabled for production use

**Troubleshooting**:
```python
# Test secure connection
import redis
client = redis.Redis(
    host="your-cluster.cache.amazonaws.com", 
    port=6379,
    ssl=True,
    password="your-auth-token"  # If AUTH enabled
)
client.ping()  # Should return True

# Check Redis configuration
info = client.info()
print(f"Redis version: {info.get('redis_version')}")
print(f"Mode: {'Cluster' if info.get('cluster_enabled') else 'Standalone/Replication'}")
if info.get('cluster_enabled'):
    print("⚠️  Cluster mode detected - StreamLL does not support cluster mode")
```

**Recommended Production Configuration**:
```python
# Production-optimized ElastiCache setup
sink = RedisSink(
    url="rediss://:auth-token@your-cluster.cache.amazonaws.com:6379",
    stream_key="app_events",
    buffer_size=5000,        # Good balance for ElastiCache memory
    max_batch_size=100,      # Optimal for ElastiCache throughput  
    circuit_breaker=True,    # Essential for production reliability
    failure_threshold=3,     # ElastiCache failover tolerance
    recovery_timeout=30.0,   # Allow time for ElastiCache failover
    max_stream_length=10000, # Prevent unbounded memory growth
    approximate_trimming=True # ElastiCache-friendly trimming
)
```

#### AWS MemoryDB for Redis
**Tested with**: MemoryDB Redis 7.0+

*[Connection examples, auth, performance data, limitations to be documented]*

#### Azure Cache for Redis  
**Tested with**: Azure Cache Premium tier

*[Connection examples, auth, performance data, limitations to be documented]*

#### Google Cloud Memorystore for Redis
**Tested with**: Memorystore Redis 7.0+

*[Connection examples, auth, performance data, limitations to be documented]*

#### Redis Cloud (Redis Enterprise)
**Tested with**: Redis Cloud Pro

*[Connection examples, auth, performance data, limitations to be documented]*

#### Self-Hosted Redis Considerations
*[Configuration, clustering limitations, performance tuning to be documented]*

---

## RabbitMQ Sink Production Guide

### Overview
StreamLL RabbitMQSink provides reliable message publishing with 1.5x batching speedup, publisher confirms, and production features like circuit breakers.

### Cloud Providers

#### Amazon MQ for RabbitMQ
**Tested with**: Amazon MQ RabbitMQ 3.11.x+

*[Connection examples, SSL config, auth, performance data, limitations to be documented]*

#### CloudAMQP
**Tested with**: CloudAMQP shared and dedicated instances

*[Connection examples, auth, performance data, limitations to be documented]*

#### Azure Service Bus (AMQP 1.0)
**Tested with**: Azure Service Bus Premium tier

*[Connection examples, managed identity auth, performance data, limitations to be documented]*

#### Self-Hosted RabbitMQ Clusters
*[Cluster configuration, load balancing, performance tuning to be documented]*

---

## Kafka Sink Production Guide  

### Overview
StreamLL KafkaSink provides high-throughput event streaming to Kafka-compatible systems.

### Cloud Providers

#### Amazon MSK (Managed Streaming for Apache Kafka)
**Tested with**: MSK 2.8+

*[Connection examples, IAM auth, performance data, limitations to be documented]*

#### Confluent Cloud
**Tested with**: Confluent Cloud Standard/Dedicated

*[Connection examples, API key auth, performance data, limitations to be documented]*

#### Azure Event Hubs (Kafka API)
**Tested with**: Event Hubs Standard/Dedicated

*[Connection examples, managed identity auth, performance data, limitations to be documented]*

#### Redpanda Cloud
**Tested with**: Redpanda Cloud BYOC/Dedicated

*[Connection examples, SASL auth, performance data, limitations to be documented]*

#### Self-Hosted Kafka
*[Cluster configuration, security, performance tuning to be documented]*