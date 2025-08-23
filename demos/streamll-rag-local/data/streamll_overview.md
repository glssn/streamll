# StreamLL: Production Streaming Infrastructure for DSPy

StreamLL is a production-ready observability and streaming infrastructure designed specifically for DSPy applications. It provides real-time monitoring, event streaming, and persistence for LLM application workflows.

## Key Features

### Real-Time Event Streaming
StreamLL captures every LLM call, tool invocation, and application event in real-time. Events are structured with execution IDs that trace complete user sessions across multiple model interactions.

### Production-Ready Sinks
- **TerminalSink**: Beautiful Rich-formatted output for development debugging
- **RedisSink**: Production streaming to Redis Streams with circuit breaker resilience
- **Planned**: RabbitMQ, Kafka/Redpanda support for enterprise messaging

### DSPy Integration
StreamLL provides seamless callbacks for DSPy modules:
- LM callback tracking (prompts, completions, tokens, streaming)
- Tool callback tracking (retrievers, custom tools, API calls)
- Module-level instrumentation with isolated sink configurations
- Automatic execution context management

### Circuit Breaker Resilience
The RedisSink includes production resilience patterns:
- Circuit breaker with configurable failure thresholds
- Local buffering during infrastructure outages  
- Exponential backoff for connection recovery
- Graceful degradation without blocking LLM calls

## Architecture Benefits

StreamLL runs entirely on the user's infrastructure - no external dependencies or SaaS requirements. This makes it perfect for:
- Sensitive enterprise applications
- Local development environments  
- Production deployments with data sovereignty requirements
- Cost-effective observability without per-event pricing