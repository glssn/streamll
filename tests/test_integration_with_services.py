"""Integration tests that use real services when available.

These tests are marked with pytest markers and will be skipped if services aren't running.
Start services with: docker-compose -f tests/docker-compose.yml up -d
"""

import asyncio

import pytest

from streamll.event_consumer import EventConsumer
from streamll.models import StreamllEvent
from streamll.sinks.redis import RedisSink
from streamll.sinks.rabbitmq import RabbitMQSink


def service_available(host: str, port: int) -> bool:
    """Check if a service is available."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


# Skip markers for services
requires_redis = pytest.mark.skipif(
    not service_available("localhost", 6379),
    reason="Redis not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)

requires_rabbitmq = pytest.mark.skipif(
    not service_available("localhost", 5672),
    reason="RabbitMQ not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)

requires_nats = pytest.mark.skipif(
    not service_available("localhost", 4222),
    reason="NATS not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)


class TestRedisIntegration:
    """Test Redis integration with real Redis."""

    @requires_redis
    @pytest.mark.asyncio
    async def test_redis_publish_consume(self):
        """Test publishing and consuming with real Redis."""
        from nanoid import generate

        stream_key = f"test_stream_{generate(size=8)}"

        # Create sink
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)

        sink.start()

        # Publish events
        events_sent = []
        for i in range(3):
            event = StreamllEvent(
                execution_id="test-run",
                event_type="token",
                module_name="test",
                data={"token": f"word_{i}", "index": i},
            )
            events_sent.append(event)
            await sink.handle_event(event)

        # Send end event
        end_event = StreamllEvent(
            execution_id="test-run",
            event_type="end",
            module_name="test",
            data={"status": "completed"},
        )
        await sink.handle_event(end_event)
        sink.stop()

        # Create consumer
        consumer = EventConsumer(broker_url="redis://localhost:6379", target=stream_key)

        events_received = []
        done = asyncio.Event()

        @consumer.on("token")
        async def handle_token(event: StreamllEvent):
            events_received.append(event)

        @consumer.on("end")
        async def handle_end(event: StreamllEvent):
            done.set()

        # Start consumer
        await consumer.start()

        # Run consumer briefly
        consumer_task = asyncio.create_task(consumer.app.run())

        # Wait for end event or timeout
        try:
            await asyncio.wait_for(done.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for events")
        finally:
            consumer_task.cancel()
            await consumer.stop()

        # Verify events
        assert len(events_received) == 3
        for i, event in enumerate(events_received):
            assert event.event_type == "token"
            assert event.data["token"] == f"word_{i}"
            assert event.data["index"] == i


class TestRabbitMQIntegration:
    """Test RabbitMQ integration with real RabbitMQ."""

    @requires_rabbitmq
    @pytest.mark.asyncio
    async def test_rabbitmq_publish_consume(self):
        """Test publishing and consuming with real RabbitMQ."""
        from nanoid import generate

        queue = f"test_queue_{generate(size=8)}"

        # Create consumer first and start listening
        consumer = EventConsumer(
            broker_url="amqp://guest:guest@localhost:5672/", target=queue
        )

        received_event = None
        done = asyncio.Event()

        @consumer.on("error")
        async def handle_error(evt: StreamllEvent):
            nonlocal received_event
            received_event = evt
            done.set()

        # Start consumer
        await consumer.start()
        consumer_task = asyncio.create_task(consumer.app.run())
        
        # Give consumer time to set up
        await asyncio.sleep(0.5)

        # Now publish event
        sink = RabbitMQSink(
            rabbitmq_url="amqp://guest:guest@localhost:5672/", queue=queue
        )
        sink.start()

        event = StreamllEvent(
            execution_id="test-run",
            event_type="error",
            module_name="test",
            data={"error": "test_error", "code": 500},
        )
        await sink.handle_event(event)
        
        # Give time for message to be delivered
        await asyncio.sleep(0.5)
        sink.stop()

        # Wait for event or timeout
        try:
            await asyncio.wait_for(done.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for event")
        finally:
            consumer_task.cancel()
            await consumer.stop()

        # Verify event
        assert received_event is not None
        assert received_event.event_type == "error"
        assert received_event.data["error"] == "test_error"
        assert received_event.data["code"] == 500


class TestNATSIntegration:
    """Test NATS integration with real NATS."""

    @requires_nats
    @pytest.mark.asyncio
    async def test_nats_broker_creation(self):
        """Test creating NATS broker when available."""
        from streamll.brokers import create_broker

        broker = create_broker("nats://localhost:4222")

        # Test connection
        await broker.start()
        await broker.stop()

        # Verify it's the right type
        assert broker.__class__.__name__ == "NatsBroker"
