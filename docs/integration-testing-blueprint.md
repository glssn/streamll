# Integration Testing Blueprint

## Overview
This blueprint extends the existing Redis integration tests (`tests/integration/test_redis_integration.py`) to create comprehensive testing for all sinks. **Note**: Redis integration tests are already well-implemented with `@pytest.mark.redis` - this blueprint focuses on completing the testing infrastructure and filling gaps.

## Current State Analysis

### ✅ What's Already Implemented:
- **Redis Integration Tests**: `tests/integration/test_redis_integration.py` with `@pytest.mark.redis`
  - Circuit breaker and buffering tests
  - Consumer group creation
  - Stream trimming
  - Buffer overflow strategies
  - Performance throughput tests
  - URL parsing and serialization
- **Test Fixtures**: Redis client, unique stream keys, cleanup
- **Infrastructure Detection**: `is_redis_available()` check

### ❌ What's Missing:
- **RabbitMQ Integration Tests**: Only unit tests exist
- **Multi-sink Integration**: Cross-sink consistency tests
- **Reliable Test Infrastructure**: Docker setup for CI/CD
- **Performance Validation**: Benchmarking the "82x speedup" claim

## Phase 1: Complete Docker Infrastructure
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  redis-test:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      
  rabbitmq-test:
    image: rabbitmq:3-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: streamll
      RABBITMQ_DEFAULT_PASS: streamll_test
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 1.2 Create test environment script
```bash
#!/bin/bash
# scripts/test-env.sh
set -e

echo "🏗️  Setting up test infrastructure..."

# Start services
docker-compose -f docker-compose.test.yml up -d

# Wait for health checks
echo "⏳ Waiting for services to be healthy..."
timeout 60s bash -c 'until docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 2; done'

echo "✅ Test infrastructure ready"

# Set environment variables for tests
export REDIS_URL="redis://localhost:6379"
export RABBITMQ_URL="amqp://streamll:streamll_test@localhost:5672/"

echo "🧪 Running integration tests..."
uv run pytest tests/integration/ -v

echo "🧹 Cleaning up..."
docker-compose -f docker-compose.test.yml down -v
```

## Phase 2: Test Structure (Organization)

### 2.1 Directory structure
```
tests/
├── integration/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_redis_integration.py
│   ├── test_rabbitmq_integration.py
│   └── test_multi_sink_integration.py
├── sinks/
│   ├── test_redis_sink.py       # Unit tests
│   └── test_rabbitmq_sink.py    # Unit tests
└── fixtures/
    ├── redis.py                 # Redis test utilities
    └── rabbitmq.py              # RabbitMQ test utilities
```

### 2.2 Base integration test class
```python
# tests/integration/conftest.py
import pytest
import time
import redis
import asyncio
from streamll.models import StreamllEvent
from streamll.sinks.redis import RedisSink
from streamll.sinks.rabbitmq import RabbitMQSink

class IntegrationTestBase:
    """Base class for integration tests with common utilities."""
    
    @staticmethod
    def create_test_event(event_id: str = None) -> StreamllEvent:
        """Create a test event with known properties."""
        return StreamllEvent(
            event_id=event_id or f"test-{int(time.time())}",
            execution_id="test-execution",
            module_name="test.module",
            method_name="test_method",
            event_type="test",
            operation="test_op",
            data={"test": "data"},
            tags=["integration-test"]
        )
    
    @staticmethod
    def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
        """Wait for a condition to be true with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        return False

@pytest.fixture(scope="session")
def redis_client():
    """Redis client for verification."""
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    yield client
    client.close()

@pytest.fixture(scope="session") 
def rabbitmq_connection():
    """RabbitMQ connection for verification."""
    # Implementation for RabbitMQ connection verification
    pass
```

## Phase 3: Core Integration Tests (Reliability)

### 3.1 Extend Existing Redis Tests
**SKIP** - Redis integration tests already exist and are comprehensive. Instead:

1. **Review existing tests** in `tests/integration/test_redis_integration.py`
2. **Validate pipeline performance** - add benchmark test to measure the "82x speedup"
3. **Add any missing edge cases** discovered during RabbitMQ development

```python
# Add to tests/integration/test_redis_integration.py
@pytest.mark.redis
def test_pipeline_performance_benchmark(self, redis_client, unique_stream_key, cleanup_stream):
    """Benchmark pipeline vs individual writes to validate performance claims."""
    # Implementation to measure and validate the 82x speedup claim
    pass
```

### 3.2 **NEW**: RabbitMQ Integration Tests  
```python
# tests/integration/test_rabbitmq_integration.py
import pytest
import asyncio
from tests.integration.conftest import IntegrationTestBase

@pytest.mark.rabbitmq  # Use specific marker like Redis does
class TestRabbitMQIntegration(IntegrationTestBase):
    
    def test_rabbitmq_basic_event_flow(self):
        """Test complete event flow from sink to RabbitMQ."""
        sink = RabbitMQSink(
            amqp_url="amqp://streamll:streamll_test@localhost:5672/",
            exchange="test_exchange",
            routing_key="test.route"
        )
        
        event = self.create_test_event("rabbitmq-basic-001")
        
        sink.start()
        try:
            sink.handle_event(event)
            sink.flush()
            
            # Wait for async processing
            self.wait_for_condition(lambda: sink.event_queue.empty())
            
            # Verify through RabbitMQ management API or consume message
            # Implementation depends on verification strategy
            
        finally:
            sink.stop()
    
    def test_rabbitmq_worker_thread_stability(self):
        """Test that worker thread handles errors gracefully."""
        # Test worker thread doesn't crash on connection errors
        pass
        
    def test_rabbitmq_circuit_breaker_integration(self):
        """Test circuit breaker behavior with real RabbitMQ failures."""
        # Test circuit breaker opens and recovers properly
        pass
```

## Phase 4: Multi-Sink Integration (Real-world scenarios)

### 4.1 Cross-sink consistency tests
```python
# tests/integration/test_multi_sink_integration.py
@pytest.mark.integration
class TestMultiSinkIntegration(IntegrationTestBase):
    
    def test_dual_sink_consistency(self, redis_client):
        """Test same events processed by both Redis and RabbitMQ sinks."""
        redis_sink = RedisSink(url="redis://localhost:6379", stream_key="dual_test")
        rabbitmq_sink = RabbitMQSink(
            amqp_url="amqp://streamll:streamll_test@localhost:5672/",
            exchange="dual_test_exchange"
        )
        
        events = [self.create_test_event(f"dual-{i}") for i in range(10)]
        
        # Start both sinks
        redis_sink.start()
        rabbitmq_sink.start()
        
        try:
            # Send same events to both
            for event in events:
                redis_sink.handle_event(event)
                rabbitmq_sink.handle_event(event)
            
            # Flush both
            redis_sink.flush()
            rabbitmq_sink.flush()
            
            # Verify consistency
            redis_count = len(redis_client.xrange("dual_test"))
            # RabbitMQ verification logic here
            
            assert redis_count == 10
            
        finally:
            redis_sink.stop()
            rabbitmq_sink.stop()
```

## Phase 5: Performance & Load Testing (Optimization)

### 5.1 Performance benchmarks
```python
# tests/integration/test_performance.py
import time
import pytest

@pytest.mark.performance
class TestPerformance(IntegrationTestBase):
    
    def test_redis_pipeline_vs_individual_performance(self, redis_client):
        """Benchmark pipeline vs individual writes."""
        redis_client.flushdb()
        
        # Test individual writes
        start_time = time.time()
        for i in range(100):
            redis_client.xadd("individual_test", {"event": f"data-{i}"})
        individual_time = time.time() - start_time
        
        # Test pipeline writes
        start_time = time.time()
        pipeline = redis_client.pipeline()
        for i in range(100):
            pipeline.xadd("pipeline_test", {"event": f"data-{i}"})
        pipeline.execute()
        pipeline_time = time.time() - start_time
        
        # Verify improvement
        improvement_ratio = individual_time / pipeline_time
        assert improvement_ratio > 2.0  # Should be significantly faster
        
        print(f"Pipeline improvement: {improvement_ratio:.1f}x faster")
```

## Phase 6: Makefile Integration (Convenience)

### 6.1 Add to Makefile
```makefile
# Add to existing Makefile
.PHONY: test-integration test-setup test-teardown

test-setup:
	@echo "🏗️  Setting up test infrastructure..."
	docker-compose -f docker-compose.test.yml up -d
	@echo "⏳ Waiting for services..."
	@timeout 60s bash -c 'until docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; do sleep 2; done'

test-teardown:
	@echo "🧹 Cleaning up test infrastructure..."
	docker-compose -f docker-compose.test.yml down -v

test-integration: test-setup
	@echo "🧪 Running integration tests..."
	REDIS_URL="redis://localhost:6379" \
	RABBITMQ_URL="amqp://streamll:streamll_test@localhost:5672/" \
	uv run pytest tests/integration/ -v -m integration
	@$(MAKE) test-teardown

test-performance: test-setup  
	@echo "⚡ Running performance tests..."
	uv run pytest tests/integration/ -v -m performance
	@$(MAKE) test-teardown

test-all: test test-integration
```

## Success Criteria

### ✅ Phase 1 Complete When:
- Docker services start reliably
- Health checks pass consistently  
- Environment variables are set correctly

### ✅ Phase 2 Complete When:
- Test structure is clean and organized
- Base test utilities work across all tests
- Fixtures are reusable and reliable

### ✅ Phase 3 Complete When:
- Basic event flow tests pass for both sinks
- Connection resilience is validated
- Buffer/flush behavior is tested

### ✅ Phase 4 Complete When:
- Multi-sink scenarios work correctly
- Cross-sink consistency is validated
- Real-world usage patterns are tested

### ✅ Phase 5 Complete When:
- Performance claims are validated with numbers
- Load testing shows acceptable behavior
- Bottlenecks are identified and documented

## Remember the Diamond Approach:
1. **Data integrity first** - Events must not be lost
2. **Reliability second** - Tests must pass consistently  
3. **Architecture consistency** - Patterns should be uniform
4. **Speed last** - Optimize only after correctness is proven

Start with Phase 1, validate each phase completely before moving to the next.