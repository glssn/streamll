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
        
        # Verify
        assert len(events) == 3
        assert events[0].event_type == "operation.start"
        assert events[1].event_type == "custom"
        assert events[1].data["value"] == 42
        assert events[2].event_type == "operation.end"
    
    def test_circuit_breaker(self):
        """Test sink handles connection failures."""
        sink = RabbitMQSink(url="amqp://guest:guest@localhost:9999")
        sink.start()
        
        with streamll.configure(sinks=[sink]):
            with streamll.trace("test"):
                pass
        
        sink.stop()
        assert sink._circuit_open  # Circuit should open on failure