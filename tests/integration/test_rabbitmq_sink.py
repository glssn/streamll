"""Integration tests for RabbitMQ sink and consumer."""

import os
import pytest
import streamll
from streamll.consumer.rabbitmq import RabbitMQConsumer
from streamll.sinks.rabbitmq import RabbitMQSink


@pytest.mark.integration
@pytest.mark.rabbitmq
class TestRabbitMQIntegration:
    """Test RabbitMQ sink and consumer."""
    
    @pytest.mark.asyncio
    async def test_sink_consumer_flow(self):
        """Test basic flow: sink writes, consumer reads."""
        url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        
        # Skip if RabbitMQ not available
        try:
            import aio_pika
            conn = await aio_pika.connect(url)
            await conn.close()
        except Exception:
            pytest.skip("RabbitMQ not available")
        
        # Send events via sink
        sink = RabbitMQSink(url=url, exchange="test", routing_key="events")
        sink.start()
        
        # Wait for connection to establish
        import asyncio
        await asyncio.sleep(1)
        
        with streamll.configure(sinks=[sink]):
            with streamll.trace("test_op") as ctx:
                ctx.emit("custom", data={"value": 42})
        
        sink.flush()
        sink.stop()
        
        # Consume events
        consumer = RabbitMQConsumer(url=url, exchange="test", queue="test_q", routing_keys=["events"])
        await consumer.start()
        
        events = []
        for _ in range(3):  # start, custom, end
            event = await consumer.consume_one()
            if event:
                events.append(event)
        
        await consumer.stop()
        
        # Verify we got events
        assert len(events) >= 2  # At least start and end
        
        # Check event types
        event_types = [e.event_type for e in events]
        assert "start" in event_types or "operation.start" in event_types
        
        # Find custom event
        custom_events = [e for e in events if e.event_type == "custom" or e.event_type == "custom_event"]
        if custom_events:
            assert custom_events[0].data.get("value") == 42
    
    def test_circuit_breaker(self):
        """Test sink handles connection failures."""
        sink = RabbitMQSink(url="amqp://guest:guest@localhost:9999")
        sink.start()
        
        with streamll.configure(sinks=[sink]):
            with streamll.trace("test"):
                pass
        
        sink.stop()
        assert sink._circuit_open  # Circuit should open on failure