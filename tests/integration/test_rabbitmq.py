"""RabbitMQ integration tests requiring real RabbitMQ server."""

import asyncio
import os

import pytest
from nanoid import generate

import streamll
from streamll.event_consumer import EventConsumer
from streamll.models import StreamllEvent
from streamll.sinks.rabbitmq import RabbitMQSink


def service_available(host: str = "localhost", port: int = 5672) -> bool:
    """Check if RabbitMQ is available."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


requires_rabbitmq = pytest.mark.skipif(
    not service_available("localhost", 5672),
    reason="RabbitMQ not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)


class TestRabbitMQIntegration:
    """Test RabbitMQ integration with real RabbitMQ."""

    @requires_rabbitmq
    @pytest.mark.asyncio
    async def test_rabbitmq_publish_consume(self):
        """Test publishing and consuming with real RabbitMQ."""
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

    @requires_rabbitmq
    @pytest.mark.asyncio
    async def test_streamll_context_with_rabbitmq(self):
        """Test streamll context manager with RabbitMQ sink."""
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        queue = f"test_queue_{generate(size=8)}"

        # Consumer side - start first
        consumer = EventConsumer(url, target=queue)
        events = []

        @consumer.on("start")
        async def handle_start(event):
            events.append(event)

        @consumer.on("custom")
        async def handle_custom(event):
            events.append(event)

        @consumer.on("end")
        async def handle_end(event):
            events.append(event)

        # Start consumer
        await consumer.start()
        task = asyncio.create_task(consumer.app.run())
        
        # Give consumer time to set up
        await asyncio.sleep(0.5)

        # Producer side
        sink = RabbitMQSink(rabbitmq_url=url, queue=queue)
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("test_op") as ctx:
            ctx.emit("custom", data={"value": 42})

        sink.stop()
        
        # Wait for events
        await asyncio.sleep(1.5)
        task.cancel()
        await consumer.stop()

        # Verify events
        assert len(events) >= 2
        event_types = [e.event_type for e in events]
        assert "start" in event_types
        assert "end" in event_types

        custom_events = [e for e in events if e.event_type == "custom"]
        if custom_events:
            assert custom_events[0].data.get("value") == 42