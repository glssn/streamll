"""Shared test fixtures and configuration for streamll tests."""

import asyncio
import os
import socket

import pytest

from streamll.models import StreamllEvent


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_event():
    """Sample StreamllEvent for testing."""
    return StreamllEvent(
        execution_id="test_exec_123",
        event_type="start",
        operation="test_operation",
        data={"key": "value"},
        tags={"test": "true"},
    )


@pytest.fixture
def sample_events():
    """List of sample StreamllEvents for testing."""
    return [
        StreamllEvent(
            execution_id="exec_1",
            event_type="start",
            operation="operation_1",
            data={"input": "test1"},
        ),
        StreamllEvent(
            execution_id="exec_1",
            event_type="end",
            operation="operation_1",
            data={"output": "result1"},
        ),
        StreamllEvent(
            execution_id="exec_2",
            event_type="error",
            operation="operation_2",
            data={"error": "Something went wrong"},
        ),
    ]


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "event_type": "token",
        "module_name": "TestModule",
        "data": {"token": "hello", "field": "answer"},
    }


# Redis fixtures using streamll interfaces
def _is_service_available(host: str = "localhost", port: int = 6379) -> bool:
    """Check if service is available via socket connection."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture(scope="function")
def redis_client():
    """Provide Redis client for integration tests."""
    if not _is_service_available("localhost", 6379):
        pytest.skip("Redis not available")

    try:
        import redis
    except ImportError:
        pytest.skip("redis package not installed")

    client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
        socket_connect_timeout=2,
    )

    # Test connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Cannot connect to Redis")

    yield client

    # Cleanup: flush test database
    if os.getenv("REDIS_TEST_FLUSH", "").lower() == "true":
        client.flushdb()
