# Tests

## Quick Start

```bash
# Run all unit tests (fast, no infrastructure needed)
uv run pytest -m unit

# Run integration tests (requires Redis + RabbitMQ)
uv run pytest -m integration

# Run performance benchmarks  
uv run pytest -m performance

# Run specific sink tests
uv run pytest -m redis
uv run pytest -m rabbitmq
```

## Test Categories

### 🚀 Unit Tests (`-m unit`)
- **Fast**: < 1 second per test
- **No dependencies**: No Redis, RabbitMQ, or external services
- **Mock everything**: External connections are mocked
- **Run frequently**: Every code change

```bash
uv run pytest -m unit
```

### 🔗 Integration Tests (`-m integration`) 
- **Real infrastructure**: Requires actual Redis/RabbitMQ instances
- **End-to-end**: Tests complete event flow through real systems
- **Slower**: 1-10 seconds per test
- **CI/Production validation**: Ensures real-world compatibility

```bash
# Requires running infrastructure
uv run pytest -m integration
```

### ⚡ Performance Tests (`-m performance`)
- **Benchmarking**: Validates performance claims (Redis 12x, RabbitMQ 1.5x speedup)
- **Throughput testing**: Events/second measurements
- **Slowest**: 10+ seconds per test
- **Release validation**: Run before major releases

```bash
uv run pytest -m performance -s  # -s shows benchmark output
```

## Infrastructure Setup

### Option 1: Docker Compose (Recommended)
```bash
# From project root:
make docker-up      # Starts tests/docker-compose.yml
make docker-down    # Stops infrastructure

# Or directly from tests directory:
docker-compose up -d
docker-compose down
```

### Option 2: Local Installation
```bash
# Redis
brew install redis
brew services start redis

# RabbitMQ  
brew install rabbitmq
brew services start rabbitmq
```

## Running Tests

### Development Workflow
```bash
# 1. Quick feedback loop (unit tests)
uv run pytest -m unit

# 2. Feature validation (integration tests for specific sink)
uv run pytest -m "integration and redis"

# 3. Full validation (all integration tests)
uv run pytest -m integration

# 4. Performance validation (before PR)
uv run pytest -m performance
```

### CI/CD Pipeline
```bash
# Stage 1: Fast validation
uv run pytest -m unit

# Stage 2: Integration validation (parallel)
uv run pytest -m "integration and redis" &
uv run pytest -m "integration and rabbitmq" &
wait

# Stage 3: Performance validation (release only)
uv run pytest -m performance
```

## Directory Structure

```
tests/
├── README.md                          # This file
├── docker-compose.yml                 # Test infrastructure (Redis + RabbitMQ)
├── conftest.py                        # Shared fixtures
├── core/                              # Core functionality tests
│   └── test_models.py
├── fixtures/                          # Test fixtures and helpers
│   ├── redis.py
│   └── rabbitmq.py
├── integration/                       # Integration tests (-m integration)
│   ├── test_redis_integration.py     # Also: -m redis, -m performance
│   ├── test_rabbitmq_integration.py  # Also: -m rabbitmq, -m performance  
│   └── test_multi_sink_integration.py
├── instrumentation/                   # DSPy instrumentation tests
│   └── test_decorator.py
└── sinks/                            # Sink unit tests (-m unit)
    ├── test_redis_sink.py
    ├── test_rabbitmq_sink.py
    ├── test_redis_data_loss_bug.py   # Bug regression tests
    ├── test_redis_delay_mutation_bug.py
    └── test_redis_pipeline_performance.py
```

## Writing Tests

### Unit Test Example
```python
import pytest
from unittest.mock import Mock
from streamll.sinks.redis import RedisSink

@pytest.mark.unit
def test_redis_sink_serialization():
    """Unit test - no real Redis needed."""
    sink = RedisSink(url="redis://fake")
    
    # Mock the Redis client
    sink._redis_client = Mock()
    
    # Test serialization logic
    event = create_test_event()
    serialized = sink._serialize_event(event)
    
    assert "event_id" in serialized
```

### Integration Test Example
```python
import pytest
import redis
from streamll.sinks.redis import RedisSink

@pytest.mark.integration
@pytest.mark.redis  
def test_redis_real_connection():
    """Integration test - requires real Redis."""
    # Assumes Redis is running on localhost:6379
    sink = RedisSink(url="redis://localhost:6379")
    sink.start()
    
    event = create_test_event()
    sink.handle_event(event)
    
    # Verify in real Redis
    client = redis.Redis(host="localhost", port=6379)
    assert client.xlen("streamll_events") > 0
    
    sink.stop()
```

### Performance Test Example
```python
import pytest
import time
from streamll.sinks.redis import RedisSink

@pytest.mark.performance
@pytest.mark.redis
def test_redis_pipeline_performance():
    """Performance test - validates speedup claims."""
    # Measure pipeline vs individual performance
    # Assert speedup > 5x (realistic expectation)
    assert speedup > 5.0
```

## Debugging Failed Tests

### Unit Test Failures
```bash
# Run with verbose output
uv run pytest -m unit -v

# Run specific test
uv run pytest tests/unit/test_models.py::test_event_creation -v

# Debug with pdb
uv run pytest -m unit --pdb
```

### Integration Test Failures
```bash
# Check if infrastructure is running
docker-compose -f docker-compose.test.yml ps

# Test Redis connection manually
redis-cli ping

# Test RabbitMQ connection
curl -u guest:guest http://localhost:15672/api/overview

# Run single integration test
uv run pytest tests/integration/test_redis_integration.py::test_basic_event_streaming -s -v
```

### Performance Test Failures
```bash
# Run with output to see benchmark numbers
uv run pytest -m performance -s -v

# Check system load during tests
uv run pytest -m performance -s --tb=short
```

## Environment Variables

```bash
# Optional: Override default URLs
export REDIS_URL="redis://localhost:6379"
export RABBITMQ_URL="amqp://guest:guest@localhost:5672/"

# Optional: Skip slow tests
export SKIP_SLOW_TESTS=1
```

## Best Practices

### ✅ Do
- **Run unit tests frequently** during development
- **Mock external dependencies** in unit tests
- **Use real infrastructure** for integration tests
- **Clean up after integration tests** (fixtures with cleanup)
- **Use descriptive test names** that explain what's being tested

### ❌ Don't  
- **Mix unit and integration logic** in the same test
- **Leave infrastructure running** after tests
- **Skip performance tests** before releases
- **Hard-code URLs** - use environment variables or fixtures
- **Test implementation details** - test behavior, not internals

