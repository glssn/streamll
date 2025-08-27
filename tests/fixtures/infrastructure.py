"""Universal infrastructure testing utilities for all sink types.

This module provides a common interface for testing Redis, RabbitMQ,
and other infrastructure components using consistent patterns.
"""

import socket
import time
from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Protocol

import pytest


class InfrastructureClient(Protocol):
    """Protocol for infrastructure test clients."""

    def cleanup(self) -> None:
        """Clean up test resources."""
        ...

    def ping(self) -> bool:
        """Test connectivity."""
        ...


class InfrastructureTester(ABC):
    """Abstract base for testing infrastructure connectivity and resilience."""

    @staticmethod
    @abstractmethod
    def is_available(host: str, port: int) -> bool:
        """Check if infrastructure is available."""
        ...

    @staticmethod
    @abstractmethod
    def wait_for_connection(client: Any, max_retries: int = 10, delay: float = 0.5) -> bool:
        """Wait for connection to be available."""
        ...

    @staticmethod
    @contextmanager
    @abstractmethod
    def simulate_connection_failure(client: Any) -> Generator[None, None, None]:
        """Simulate connection failure for resilience testing."""
        ...


def check_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Generic port connectivity check."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


class ConnectionResilienceTester:
    """Universal connection resilience testing patterns."""

    @staticmethod
    def test_reconnection_after_failure(
        client: Any, failure_context: Any, wait_for_connection_fn: Any, max_retries: int = 10
    ) -> None:
        """Generic pattern for testing reconnection after infrastructure failure."""
        # Verify initial connection
        assert client.ping()

        # Simulate connection failure
        with failure_context(client), pytest.raises((ConnectionError, Exception)):
            client.ping()

        # Verify reconnection
        assert wait_for_connection_fn(client, max_retries=max_retries)


def generate_unique_identifier(prefix: str = "test") -> str:
    """Generate unique identifier for test isolation."""
    return f"{prefix}_{int(time.time() * 1000)}_{id(object())}"


class TestResourceTracker:
    """Track test resources for cleanup across different infrastructure types."""

    def __init__(self):
        self.redis_keys: set[str] = set()
        self.redis_streams: set[str] = set()
        self.rabbitmq_queues: set[str] = set()
        self.rabbitmq_exchanges: set[str] = set()

    def track_redis_key(self, key: str) -> None:
        """Track Redis key for cleanup."""
        self.redis_keys.add(key)

    def track_redis_stream(self, stream: str) -> None:
        """Track Redis stream for cleanup."""
        self.redis_streams.add(stream)

    def track_rabbitmq_queue(self, queue: str) -> None:
        """Track RabbitMQ queue for cleanup."""
        self.rabbitmq_queues.add(queue)

    def track_rabbitmq_exchange(self, exchange: str) -> None:
        """Track RabbitMQ exchange for cleanup."""
        self.rabbitmq_exchanges.add(exchange)


@pytest.fixture
def infrastructure_available():
    """Check which infrastructure services are available for testing."""
    return {
        "redis": check_port_open("localhost", 6379),
        "rabbitmq": check_port_open("localhost", 5672),
    }


@pytest.fixture
def test_resource_tracker():
    """Provide resource tracker for test isolation."""
    return TestResourceTracker()


def skip_if_infrastructure_unavailable(infrastructure_type: str):
    """Decorator to skip tests if infrastructure is not available."""

    def decorator(test_func):
        def wrapper(*args, **kwargs):
            # Extract infrastructure_available fixture
            infrastructure_available = None
            for arg in args:
                if hasattr(arg, "get") and infrastructure_type in arg:
                    infrastructure_available = arg
                    break

            if not infrastructure_available or not infrastructure_available.get(
                infrastructure_type
            ):
                pytest.skip(f"{infrastructure_type} not available for testing")

            return test_func(*args, **kwargs)

        return wrapper

    return decorator
