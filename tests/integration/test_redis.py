"""Redis integration tests requiring real Redis server."""

import asyncio

import pytest
from nanoid import generate

from streamll.event_consumer import EventConsumer
from streamll.models import StreamllEvent
from streamll.sinks.redis import RedisSink


def service_available(host: str = "localhost", port: int = 6379) -> bool:
    """Check if Redis is available."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


requires_redis = pytest.mark.skipif(
    not service_available("localhost", 6379),
    reason="Redis not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)


class TestRedisIntegration:
    """Test Redis integration with real Redis."""

    @requires_redis
    @pytest.mark.asyncio
    async def test_redis_publish_consume(self):
        """Test publishing and consuming with real Redis."""
        stream_key = f"test_stream_{generate(size=8)}"

        # Create consumer first and start listening
        consumer = EventConsumer(
            broker_url="redis://localhost:6379", target=stream_key
        )

        received_events = []
        done = asyncio.Event()

        @consumer.on("token")
        async def handle_token(event: StreamllEvent):
            received_events.append(event)
            if len(received_events) >= 3:
                done.set()

        # Start consumer
        await consumer.start()
        consumer_task = asyncio.create_task(consumer.app.run())
        
        # Give consumer time to set up
        await asyncio.sleep(0.5)

        # Create sink and publish events
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        sink.start()

        # Publish multiple events
        for i in range(3):
            event = StreamllEvent(
                execution_id="test-run",
                event_type="token",
                module_name="test",
                data={"token": f"word_{i}", "index": i},
            )
            await sink.handle_event(event)

        # Wait for events
        try:
            await asyncio.wait_for(done.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for events")
        finally:
            consumer_task.cancel()
            await consumer.stop()
            sink.stop()

        # Verify events
        assert len(received_events) == 3
        for i, event in enumerate(received_events):
            assert event.event_type == "token"
            assert event.data["token"] == f"word_{i}"
            assert event.data["index"] == i

    @requires_redis
    @pytest.mark.asyncio
    async def test_redis_sink_basic_write(self):
        """Test Redis sink can write events."""
        stream_key = f"test_stream_{generate(size=8)}"
        
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        sink.start()

        # Test event
        event = StreamllEvent(execution_id="test", event_type="test")
        await sink.handle_event(event)

        sink.stop()
        # If we get here without exception, the write succeeded