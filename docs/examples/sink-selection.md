# Choosing Your StreamLL Sink

Real-world examples showing how to select and configure the right streaming backend for your use case.

## 🎯 Decision Tree

```
Your Use Case?
├── 📚 Learning/Development
│   └── → TerminalSink (zero setup)
├── 🚀 Production API/Dashboard  
│   └── → RedisSink (high performance)
├── 🏢 Enterprise/Compliance
│   └── → RabbitMQSink (durability + routing)
└── 🔧 Multi-environment
    └── → Multiple sinks
```

## Example 1: Startup Development Team

**Scenario**: Building a RAG chatbot, need fast iteration

```python
import streamll
from streamll.sinks import TerminalSink

# Zero setup - start coding immediately
streamll.configure(sinks=[TerminalSink()])

@streamll.instrument
class ChatBot(dspy.Module):
    def __init__(self):
        self.llm = dspy.ChainOfThought("question -> answer")
    
    def forward(self, question):
        return self.llm(question=question)

# Beautiful console output while developing:
# [16:31:42] ▶ llm_call (abc123)
# [16:31:43] • llm_call (abc123) 'The answer is'
# [16:31:44] ■ llm_call (abc123) {"tokens": 42}
```

**Why TerminalSink:**
- ✅ Instant feedback during development
- ✅ No infrastructure to manage
- ✅ Perfect for debugging and demos

## Example 2: SaaS Platform with Dashboard

**Scenario**: Customer-facing AI platform, need real-time monitoring

```python
import streamll
from streamll.sinks import RedisSink
import os

# High-performance streaming for production
redis_sink = RedisSink(
    url=os.getenv("REDIS_URL", "redis://localhost:6379"),
    stream_key="ai_platform_events",
    max_buffer_size=10000,
    circuit_breaker=True,
    failure_threshold=5,
    recovery_timeout=30.0
)

streamll.configure(sinks=[redis_sink])

@streamll.instrument  
class DocumentAnalyzer(dspy.Module):
    def forward(self, document):
        # Events automatically stream to Redis
        # → Real-time dashboard updates
        # → Customer usage analytics  
        # → Performance monitoring
        return self.analyze(document)
```

**Real-time Consumer (Dashboard Backend):**
```python
import redis
import json

r = redis.Redis.from_url(os.getenv("REDIS_URL"))

# Live dashboard updates
while True:
    events = r.xread({'ai_platform_events': '$'}, block=1000)
    for stream, messages in events:
        for msg_id, fields in messages:
            event = json.loads(fields[b'event'])
            
            # Update customer dashboard
            update_customer_metrics(
                customer_id=event['tags'].get('customer_id'),
                operation=event['operation'],
                tokens=event['data'].get('tokens', 0)
            )
```

**Why RedisSink:**
- ✅ Sub-5ms latency for real-time dashboards
- ✅ 100K+ events/second throughput
- ✅ Built-in circuit breaker for reliability
- ✅ Perfect for microservices architecture

## Example 3: Financial Services (Compliance)

**Scenario**: Bank using AI for loan decisions, need audit trails

```python
import streamll
from streamll.sinks import RabbitMQSink
import os

# Enterprise message queuing for compliance
compliance_sink = RabbitMQSink(
    amqp_url=os.getenv("RABBITMQ_URL"),
    exchange="financial_ai_audit", 
    routing_key="loan.{operation}.{event_type}",
    durable=True,  # Survive server restarts
    circuit_breaker=True,
    max_retries=5
)

streamll.configure(sinks=[compliance_sink])

@streamll.instrument(tags={"department": "lending", "risk_level": "high"})
class LoanDecisionEngine(dspy.Module):
    def forward(self, application):
        # Every AI decision permanently logged
        # → Regulatory audit trail
        # → Risk monitoring alerts
        # → Compliance reporting
        return self.evaluate_loan(application)
```

**Compliance Consumer (Audit System):**
```python
import pika
import json

# Permanent storage for regulators
connection = pika.BlockingConnection(
    pika.URLParameters(os.getenv("RABBITMQ_URL"))
)
channel = connection.channel()

# Declare durable queue for audit trail
channel.queue_declare(queue='loan_audit_trail', durable=True)
channel.queue_bind(
    exchange='financial_ai_audit',
    queue='loan_audit_trail', 
    routing_key='loan.#'  # All loan events
)

def store_audit_event(ch, method, properties, body):
    event = json.loads(body)
    
    # Store in compliance database
    audit_db.store_event(
        timestamp=event['timestamp'],
        loan_id=event['tags'].get('loan_id'), 
        ai_decision=event['data'],
        officer_id=event['tags'].get('officer_id')
    )
    
    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_consume(queue='loan_audit_trail', on_message_callback=store_audit_event)
channel.start_consuming()
```

**Why RabbitMQSink:**
- ✅ Durable queues survive system failures
- ✅ Message routing for different departments  
- ✅ Dead letter queues for error handling
- ✅ Perfect for regulatory compliance

## Example 4: Multi-Environment Deployment

**Scenario**: Standardize across dev/staging/prod environments

```python
import streamll
from streamll.sinks import TerminalSink, RedisSink, RabbitMQSink
import os

def configure_streamll_for_environment():
    """Configure appropriate sinks for each environment."""
    
    env = os.getenv("ENVIRONMENT", "development")
    sinks = []
    
    if env == "development":
        # Local development: Terminal only
        sinks = [TerminalSink()]
        
    elif env == "staging":
        # Staging: Terminal + Redis for integration testing
        sinks = [
            TerminalSink(),  # Developers can still see output
            RedisSink(
                url=os.getenv("REDIS_URL"),
                stream_key="staging_ai_events",
                circuit_breaker=True
            )
        ]
        
    elif env == "production":
        # Production: Redis for real-time + RabbitMQ for durability
        sinks = [
            RedisSink(
                url=os.getenv("REDIS_CLUSTER_URL"),
                stream_key="prod_ai_events", 
                circuit_breaker=True,
                failure_threshold=3,
                recovery_timeout=60.0
            ),
            RabbitMQSink(
                amqp_url=os.getenv("RABBITMQ_CLUSTER_URL"),
                exchange="production_ai",
                routing_key="ai.{module_name}.{event_type}",
                durable=True,
                circuit_breaker=True
            )
        ]
    
    streamll.configure(sinks=sinks)
    return sinks

# Use in your application
sinks = configure_streamll_for_environment()

@streamll.instrument
class ProductionAIService(dspy.Module):
    def forward(self, request):
        # Events automatically routed to appropriate sinks
        # Dev: Beautiful terminal output
        # Staging: Terminal + Redis testing  
        # Prod: Redis dashboards + RabbitMQ audit
        return self.process(request)
```

## Example 5: Custom Sink Routing

**Scenario**: Route different events to different systems

```python
import streamll
from streamll.sinks import RedisSink, RabbitMQSink

# Real-time monitoring sink
monitoring_sink = RedisSink(
    url="redis://monitoring-cluster:6379",
    stream_key="ai_monitoring",
    circuit_breaker=True
)

# Audit trail sink  
audit_sink = RabbitMQSink(
    amqp_url="amqp://audit-cluster:5672/",
    exchange="ai_audit",
    routing_key="audit.{module_name}.{event_type}",
    durable=True
)

# Error alerting sink
alerts_sink = RabbitMQSink(
    amqp_url="amqp://alerts-cluster:5672/", 
    exchange="ai_alerts",
    routing_key="alert.{operation}.error",
    durable=True
)

streamll.configure(sinks=[monitoring_sink, audit_sink, alerts_sink])

@streamll.instrument(tags={"service": "risk_engine", "criticality": "high"})
class RiskEngine(dspy.Module):
    def forward(self, transaction):
        # All events go to monitoring (Redis)
        # All events go to audit (RabbitMQ) 
        # Error events trigger alerts (RabbitMQ)
        return self.analyze_risk(transaction)
```

## Installation Commands by Use Case

```bash
# Development only
pip install streamll

# SaaS platform with dashboards
pip install streamll[redis]

# Enterprise with compliance  
pip install streamll[rabbitmq]

# Multi-environment production
pip install streamll[all]
```

## Performance Comparison

| Sink | Latency | Throughput | Durability | Setup |
|------|---------|------------|------------|-------|
| **Terminal** | <1ms | 10K/sec | None | Zero |
| **Redis** | 1-5ms | 100K/sec | Memory | Minimal |
| **RabbitMQ** | 2-10ms | 50K/sec | Disk | Moderate |

## Monitoring Your Setup

```python
# Check sink health
def check_streamll_health():
    for sink in streamll.get_configured_sinks():
        print(f"✅ {sink.__class__.__name__}: {sink.is_running}")
        
        if hasattr(sink, 'failures'):
            if sink.failures > 0:
                print(f"⚠️  Recent failures: {sink.failures}")
        
        if hasattr(sink, 'circuit_open') and sink.circuit_open:
            print(f"🔴 Circuit breaker: OPEN")

# Run in your health check endpoint
check_streamll_health()
```

Choose the setup that matches your architecture! 🎯