"""Redis test fixtures and utilities following open-source best practices."""

import socket
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
import redis


class RedisTestClient:
    """Test wrapper for Redis client with cleanup capabilities."""

    def __init__(self, redis_client: redis.Redis):
        self.client = redis_client
        self._test_keys: set[str] = set()
        self._test_streams: set[str] = set()

    def set(self, key: str, value: Any, **kwargs) -> None:
        """Set with automatic cleanup tracking."""
        self._test_keys.add(key)
        return self.client.set(key, value, **kwargs)

    def xadd(self, stream: str, fields: dict[str, Any], **kwargs) -> str:
        """Add to stream with automatic cleanup tracking."""
        self._test_streams.add(stream)
        return self.client.xadd(stream, fields, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Delegate to underlying Redis client."""
        return getattr(self.client, name)

    def cleanup(self) -> None:
        """Clean up all test data."""
        if self._test_keys:
            self.client.delete(*self._test_keys)
            self._test_keys.clear()

        if self._test_streams:
            self.client.delete(*self._test_streams)
            self._test_streams.clear()


def is_redis_available(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is available at the given host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


@contextmanager
def redis_connection_failure(redis_client: redis.Redis) -> Generator[None, None, None]:
    """Context manager to simulate Redis connection failure."""
    # Store original connection pool
    original_pool = redis_client.connection_pool

    # Create a broken connection pool
    broken_pool = redis.ConnectionPool(host="127.0.0.1", port=1, max_connections=1)
    redis_client.connection_pool = broken_pool

    try:
        yield
    finally:
        # Restore original connection pool
        redis_client.connection_pool = original_pool


@pytest.fixture(scope="session")
def redis_server_available() -> bool:
    """Check if Redis server is available for testing."""
    return is_redis_available()


@pytest.fixture(scope="function")
def redis_client(redis_server_available: bool) -> Generator[RedisTestClient, None, None]:
    """Provide a clean Redis client for each test with automatic cleanup."""
    if not redis_server_available:
        pytest.skip("Redis server not available for testing")

    client = redis.Redis(
        host="localhost",
        port=6379,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=10,
    )

    # Test connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Cannot connect to Redis server")

    test_client = RedisTestClient(client)

    yield test_client

    # Cleanup after test
    test_client.cleanup()


@pytest.fixture(scope="function")
def isolated_redis_client(redis_client: RedisTestClient) -> Generator[RedisTestClient, None, None]:
    """Provide isolated Redis client that uses a test-specific key prefix."""
    test_id = f"test_{int(time.time() * 1000)}"

    class IsolatedRedisClient(RedisTestClient):
        def _prefix_key(self, key: str) -> str:
            return f"{test_id}:{key}"

        def set(self, key: str, value: Any, **kwargs) -> None:
            prefixed_key = self._prefix_key(key)
            self._test_keys.add(prefixed_key)
            return self.client.set(prefixed_key, value, **kwargs)

        def get(self, key: str) -> Any:
            return self.client.get(self._prefix_key(key))

        def xadd(self, stream: str, fields: dict[str, Any], **kwargs) -> str:
            prefixed_stream = self._prefix_key(stream)
            self._test_streams.add(prefixed_stream)
            return self.client.xadd(prefixed_stream, fields, **kwargs)

        def xread(self, streams: dict[str, str], **kwargs) -> list:
            prefixed_streams = {self._prefix_key(k): v for k, v in streams.items()}
            return self.client.xread(prefixed_streams, **kwargs)

    isolated_client = IsolatedRedisClient(redis_client.client)
    yield isolated_client
    isolated_client.cleanup()


@pytest.fixture(scope="function")
def redis_stream_name() -> str:
    """Generate unique stream name for tests."""
    return f"test_stream_{int(time.time() * 1000)}_{id(object())}"


class RedisConnectionTester:
    """Utility class for testing Redis connection resilience."""

    @staticmethod
    def wait_for_connection(client: redis.Redis, max_retries: int = 10, delay: float = 0.5) -> bool:
        """Wait for Redis connection to be available."""
        for _ in range(max_retries):
            try:
                client.ping()
                return True
            except redis.ConnectionError:
                time.sleep(delay)
        return False

    @staticmethod
    def test_reconnection_after_failure(client: redis.Redis) -> None:
        """Test that client can reconnect after connection failure."""
        # Verify initial connection
        assert client.ping()

        # Simulate connection failure and recovery
        with redis_connection_failure(client), pytest.raises(redis.ConnectionError):
            client.ping()

        # Verify reconnection (may need retries for connection pool reset)
        assert RedisConnectionTester.wait_for_connection(client, max_retries=5)
