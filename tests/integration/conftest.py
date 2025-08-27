"""Shared fixtures and base classes for integration tests."""

import os
import time
from datetime import UTC, datetime

import pytest
import redis

from streamll.models import StreamllEvent
from streamll.sinks.rabbitmq import RabbitMQSink
from streamll.sinks.redis import RedisSink


class IntegrationTestBase:
    """Base class for integration tests with common utilities.

    Following the Diamond Approach:
    1. Data integrity first - Events must not be lost
    2. Reliability second - Tests must pass consistently
    3. Architecture consistency - Patterns should be uniform
    4. Speed last - Optimize only after correctness is proven
    """

    @staticmethod
    def create_test_event(event_id: str | None = None, data: dict | None = None) -> StreamllEvent:
        """Create a test event with known properties for verification.

        Args:
            event_id: Optional specific event ID
            data: Optional custom data payload

        Returns:
            StreamllEvent with predictable, verifiable properties
        """
        return StreamllEvent(
            event_id=event_id or f"test-{int(time.time() * 1000)}",
            execution_id="test-execution-001",
            module_name="test.module",
            method_name="test_method",
            event_type="integration_test",
            operation="test_operation",
            data=data or {"test": "integration_data", "timestamp": time.time()},
            tags={"environment": "test", "type": "integration"},
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1) -> bool:
        """Wait for a condition to be true with timeout.

        Args:
            condition_func: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            interval: Polling interval in seconds

        Returns:
            True if condition was met, False if timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(interval)
        return False

    @staticmethod
    def create_unique_key(prefix: str) -> str:
        """Create unique key for test isolation."""
        timestamp = int(time.time() * 1000000)  # microseconds for uniqueness
        return f"{prefix}_{timestamp}"


@pytest.fixture(scope="session")
def redis_client():
    """Redis client for verification in integration tests.

    Uses session scope to avoid connection overhead between tests.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    client = redis.Redis.from_url(redis_url, decode_responses=True)

    # Test connection
    try:
        client.ping()
    except redis.ConnectionError as e:
        pytest.skip(f"Redis not available for integration tests: {e}")

    yield client
    client.close()


@pytest.fixture(scope="session")
def rabbitmq_url():
    """RabbitMQ connection URL for integration tests."""
    return os.getenv("RABBITMQ_URL", "amqp://streamll:streamll_test@localhost:5672/")


@pytest.fixture(scope="session")
def test_redis_sink(redis_client):
    """Redis sink factory for integration tests."""

    def _create_redis_sink(stream_key: str | None = None, **kwargs):
        """Create Redis sink with test configuration."""
        if stream_key is None:
            stream_key = f"test_stream_{int(time.time() * 1000)}"

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        sink = RedisSink(url=redis_url, stream_key=stream_key, **kwargs)
        return sink

    return _create_redis_sink


@pytest.fixture(scope="session")
def test_rabbitmq_sink(rabbitmq_url):
    """RabbitMQ sink factory for integration tests."""

    def _create_rabbitmq_sink(
        exchange: str | None = None, routing_key: str | None = None, **kwargs
    ):
        """Create RabbitMQ sink with test configuration."""
        if exchange is None:
            exchange = f"test_exchange_{int(time.time() * 1000)}"
        if routing_key is None:
            routing_key = "test.{event_type}.{operation}"

        sink = RabbitMQSink(
            amqp_url=rabbitmq_url,
            exchange=exchange,
            routing_key=routing_key,
            durable=False,  # Non-durable for faster test cleanup
            circuit_breaker=True,
            failure_threshold=3,
            recovery_timeout=1.0,  # Fast recovery for tests
            **kwargs,
        )
        return sink

    return _create_rabbitmq_sink


# Pytest markers for test organization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring real infrastructure"
    )
    config.addinivalue_line("markers", "performance: Performance and benchmark tests")
    config.addinivalue_line("markers", "slow: Slow tests that take >5 seconds")
