"""Integration tests for Redis sink with real Redis instance."""

import os
import time

import pytest
import redis

import streamll
from streamll.sinks.redis import RedisSink


@pytest.mark.integration
@pytest.mark.redis
class TestRedisSinkIntegration:
    """Test Redis sink with real Redis instance."""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client for testing."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(redis_url, decode_responses=True)

        # Check Redis is available
        try:
            client.ping()
        except redis.ConnectionError:
            pytest.skip("Redis not available")

        # Clean up test keys
        client.delete("streamll:test:*")
        yield client
        # Cleanup after test
        for key in client.keys("streamll:test:*"):
            client.delete(key)

    def test_redis_sink_basic_write(self, redis_client):
        """Test basic event writing to Redis."""
        sink = RedisSink(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"), stream_key="streamll:test:events"
        )
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("test_operation") as ctx:
            ctx.emit("custom_event", data={"value": 42})

        sink.stop()

        # Check events were written to Redis
        events = redis_client.xrange("streamll:test:events")
        assert len(events) >= 3  # start, custom, end

        # Verify custom event data
        for _event_id, event_data in events:
            if event_data.get("event_type") == "custom_event":
                assert "value" in event_data.get("data", "{}")

    def test_redis_sink_buffering(self, redis_client):
        """Test Redis sink buffers events efficiently."""
        sink = RedisSink(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            stream_key="streamll:test:buffer",
            buffer_size=10,
        )
        sink.start()

        with streamll.configure(sinks=[sink]):
            # Generate multiple events quickly
            for i in range(5):
                with streamll.trace(f"op_{i}"):
                    pass

        # Wait for flush
        time.sleep(1)
        sink.stop()

        # All events should be written
        events = redis_client.xrange("streamll:test:buffer")
        assert len(events) >= 10  # 5 operations * 2 events each

    def test_redis_sink_circuit_breaker(self, redis_client):
        """Test Redis sink handles connection failures gracefully."""
        # Use invalid Redis URL
        sink = RedisSink(
            url="redis://localhost:9999",  # Wrong port
            stream_key="streamll:test:breaker",
        )
        sink.start()

        # Should not crash when Redis unavailable
        with streamll.configure(sinks=[sink]), streamll.trace("test_op"):
            pass

        sink.stop()

        # Sink should have logged errors but not crashed
        assert sink._circuit_open

    def test_redis_sink_reconnection(self, redis_client):
        """Test Redis sink can reconnect after failure."""
        sink = RedisSink(
            url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            stream_key="streamll:test:reconnect",
        )
        sink.start()

        # Simulate connection failure by closing client
        if sink._redis_client:
            sink._redis_client.close()
        sink._circuit_open = True

        # Wait for circuit breaker timeout
        time.sleep(2)
        sink._circuit_open = False

        # Should reconnect and write
        with streamll.configure(sinks=[sink]), streamll.trace("reconnect_test"):
            pass

        sink.stop()

        # Check event was written after reconnection
        events = redis_client.xrange("streamll:test:reconnect")
        assert len(events) >= 2
