"""Integration tests for Redis sink with real Redis instance."""

import os

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

    @pytest.mark.asyncio
    async def test_redis_sink_basic_write(self, redis_client):
        """Test basic event writing to Redis."""
        import asyncio
        from streamll.event_consumer import EventConsumer
        
        stream_key = "streamll:test:events"
        
        # Set up consumer to verify events
        consumer = EventConsumer(
            broker_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            target=stream_key
        )
        
        received_events = []
        done = asyncio.Event()
        
        @consumer.on("start")
        async def handle_start(event):
            received_events.append(event)
            print(f"Received start event: {event}")
            
        @consumer.on("custom_event")
        async def handle_custom(event):
            received_events.append(event)
            print(f"Received custom event: {event}")
            done.set()
            
        @consumer.on("end")
        async def handle_end(event):
            received_events.append(event)
            print(f"Received end event: {event}")
        
        # Start consumer
        await consumer.start()
        consumer_task = asyncio.create_task(consumer.app.run())
        await asyncio.sleep(0.1)  # Let consumer start
        
        # Publish events
        sink = RedisSink(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            stream_key=stream_key,
        )
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("test_operation") as ctx:
            ctx.emit("custom_event", data={"value": 42})

        sink.stop()
        
        # Wait for events
        try:
            await asyncio.wait_for(done.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail("Did not receive expected event")
        finally:
            consumer_task.cancel()
            await consumer.stop()

        # Verify custom event data
        assert len(received_events) >= 3  # start, custom, end
        custom_events = [e for e in received_events if e.event_type == "custom_event"]
        assert len(custom_events) == 1
        custom_event = custom_events[0]
        assert custom_event.data["value"] == 42

    @pytest.mark.asyncio
    async def test_redis_sink_buffering(self, redis_client):
        """Test Redis sink buffers events efficiently."""
        import asyncio
        from streamll.event_consumer import EventConsumer
        
        stream_key = "streamll:test:buffer"
        
        # Set up consumer to count events
        consumer = EventConsumer(
            broker_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            target=stream_key
        )
        
        received_events = []
        
        @consumer.on("start")
        async def handle_start(event):
            received_events.append(event)
            
        @consumer.on("end")
        async def handle_end(event):
            received_events.append(event)
        
        # Start consumer
        await consumer.start()
        consumer_task = asyncio.create_task(consumer.app.run())
        await asyncio.sleep(0.1)  # Let consumer start
        
        # Publish events
        sink = RedisSink(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            stream_key=stream_key,
        )
        sink.start()

        with streamll.configure(sinks=[sink]):
            # Generate multiple events quickly
            for i in range(5):
                with streamll.trace(f"op_{i}"):
                    pass

        sink.stop()
        
        # Wait for events to be processed
        await asyncio.sleep(1.5)
        consumer_task.cancel()
        await consumer.stop()

        # All events should be written - 5 operations * 2 events each (start + end)
        assert len(received_events) >= 10
