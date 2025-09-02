"""Integration tests for RabbitMQ sink and consumer."""

import os

import pytest

import streamll
from streamll.sinks.rabbitmq import RabbitMQSink


@pytest.mark.integration
@pytest.mark.rabbitmq
class TestRabbitMQIntegration:
    """Test RabbitMQ sink and consumer."""

    @pytest.mark.asyncio
    async def test_sink_consumer_flow(self):
        """Test basic flow: sink writes, consumer reads."""
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

        try:
            from streamll.brokers import create_broker

            broker = create_broker(url)
            await broker.start()
            await broker.stop()
        except Exception as e:
            pytest.skip(f"RabbitMQ not available: {e}")

        from streamll.event_consumer import EventConsumer
        import asyncio

        # Consumer side - start first
        consumer = EventConsumer(url, target="test_queue")
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
        sink = RabbitMQSink(rabbitmq_url=url, queue="test_queue")
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
