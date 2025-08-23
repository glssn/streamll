# Production Patterns with StreamLL

StreamLL is designed for production LLM applications with enterprise-grade reliability and observability requirements.

## Deployment Architecture

### Infrastructure Independence
StreamLL runs entirely on your infrastructure:
- No external SaaS dependencies
- No data leaves your environment  
- Full control over data retention and compliance
- Cost-effective scaling without per-event fees

### Multi-Sink Strategies
Production deployments typically use multiple sinks:
- **TerminalSink**: Development debugging and local testing
- **RedisSink**: Real-time event streaming for dashboards
- **FileSink**: Long-term audit trails and compliance logging
- **MetricsSink**: Prometheus/Grafana integration for alerting

## Resilience Patterns

### Circuit Breaker Implementation
StreamLL's RedisSink includes production-tested resilience:

```python
sink = RedisSink(
    url="redis://localhost:6379",
    stream_key="production_events",
    circuit_breaker=True,
    failure_threshold=3,      # Open after 3 consecutive failures
    recovery_timeout=30.0,    # Try recovery every 30 seconds
    buffer_size=10000         # Buffer events during outages
)
```

### Graceful Degradation
When infrastructure fails, StreamLL continues operating:
- Events buffered locally during Redis outages
- Circuit breaker prevents cascade failures
- LLM applications continue running uninterrupted
- Automatic recovery when infrastructure returns

## Observability Best Practices

### Execution Tracing
Every event includes execution_id for complete request tracing:
- Track user sessions across multiple LLM calls
- Correlate tool usage with specific queries
- Debug complex multi-step reasoning chains
- Performance analysis of end-to-end workflows

### Error Monitoring
StreamLL captures detailed error context:
- LLM API failures and rate limiting
- Tool execution timeouts and data issues
- Infrastructure connectivity problems
- Application logic errors with full stack traces

### Performance Metrics
Built-in performance tracking:
- Token usage and API costs per execution
- Response latency distributions
- Tool execution performance
- Infrastructure health metrics