"""Integration tests for RabbitMQ sink and consumer with real RabbitMQ instance."""

import asyncio
import os
import time

import pytest

import streamll
from streamll.consumer.rabbitmq import RabbitMQConsumer
from streamll.sinks.rabbitmq import RabbitMQSink


@pytest.mark.integration
@pytest.mark.rabbitmq
class TestRabbitMQIntegration:
    """Test RabbitMQ sink and consumer with real RabbitMQ instance."""
    
    @pytest.fixture
    async def rabbitmq_cleanup(self):
        """Clean up RabbitMQ queues and exchanges."""
        # Skip if RabbitMQ not available
        try:
            import aio_pika
            
            url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
            connection = await aio_pika.connect(url)
            channel = await connection.channel()
            
            # Try to delete test exchange/queues
            try:
                await channel.exchange_delete("streamll_test")
            except Exception:
                pass
                
            try:
                await channel.queue_delete("streamll_test_events")
            except Exception:
                pass
                
            await connection.close()
            
        except Exception:
            pytest.skip("RabbitMQ not available")
            
        yield
        
        # Cleanup after test
        try:
            connection = await aio_pika.connect(url)
            channel = await connection.channel()
            
            try:
                await channel.queue_delete("streamll_test_events")
            except Exception:
                pass
                
            try:
                await channel.exchange_delete("streamll_test")
            except Exception:
                pass
                
            await connection.close()
        except Exception:
            pass
            
    @pytest.mark.asyncio
    async def test_rabbitmq_sink_consumer_flow(self, rabbitmq_cleanup):
        """Test end-to-end flow: sink writes, consumer reads."""
        # Create sink
        sink = RabbitMQSink(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            routing_key="test.events",
        )
        sink.start()
        
        # Generate events
        with streamll.configure(sinks=[sink]):
            with streamll.trace("test_operation") as ctx:
                ctx.emit("custom_event", data={"value": 42})
                
        # Flush to ensure events are sent
        sink.flush()
        
        # Create consumer
        consumer = RabbitMQConsumer(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            queue="streamll_test_events",
            routing_keys=["test.events"],
        )
        
        # Consume events
        await consumer.start()
        
        events = []
        for _ in range(3):  # Expect at least 3 events (start, custom, end)
            event = await consumer.consume_one()
            if event:
                events.append(event)
                
        await consumer.stop()
        sink.stop()
        
        # Verify events
        assert len(events) >= 3
        event_types = [e.event_type for e in events]
        assert "operation.start" in event_types
        assert "custom_event" in event_types
        assert "operation.end" in event_types
        
        # Check custom event data
        for event in events:
            if event.event_type == "custom_event":
                assert event.data.get("value") == 42
                
    @pytest.mark.asyncio
    async def test_rabbitmq_consumer_handlers(self, rabbitmq_cleanup):
        """Test consumer with event handlers."""
        # Create sink
        sink = RabbitMQSink(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            routing_key="handler.events",
        )
        sink.start()
        
        # Generate events
        with streamll.configure(sinks=[sink]):
            with streamll.trace("handler_test") as ctx:
                ctx.emit("test_event", data={"message": "hello"})
                
        sink.flush()
        sink.stop()
        
        # Create consumer with handlers
        consumer = RabbitMQConsumer(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            queue="streamll_test_handlers",
            routing_keys=["handler.events"],
        )
        
        received_events = []
        
        @consumer.on("test_event")
        def handle_test_event(event):
            received_events.append(event)
            
        # Start consumer and process events
        await consumer.start()
        
        # Consume with timeout
        start_time = time.time()
        while len(received_events) == 0 and time.time() - start_time < 5:
            event = await consumer.consume_one()
            if event:
                consumer._dispatch_event(event)
                
        await consumer.stop()
        
        # Verify handler was called
        assert len(received_events) == 1
        assert received_events[0].event_type == "test_event"
        assert received_events[0].data["message"] == "hello"
        
    def test_rabbitmq_sync_consumer(self, rabbitmq_cleanup):
        """Test synchronous consumer interface."""
        # Run async cleanup
        loop = asyncio.new_event_loop()
        loop.run_until_complete(rabbitmq_cleanup.__anext__())
        
        # Create sink and send events
        sink = RabbitMQSink(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            routing_key="sync.events",
        )
        sink.start()
        
        with streamll.configure(sinks=[sink]):
            with streamll.trace("sync_test"):
                pass
                
        sink.flush()
        sink.stop()
        
        # Create consumer
        consumer = RabbitMQConsumer(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            queue="streamll_test_sync",
            routing_keys=["sync.events"],
        )
        
        # Use iterator interface
        events = []
        for event in consumer.iter_events(max_events=2):
            events.append(event)
            
        # Verify events
        assert len(events) == 2
        assert events[0].event_type == "operation.start"
        assert events[1].event_type == "operation.end"
        
    @pytest.mark.asyncio
    async def test_rabbitmq_circuit_breaker(self):
        """Test RabbitMQ sink handles connection failures gracefully."""
        # Use invalid RabbitMQ URL
        sink = RabbitMQSink(
            url="amqp://guest:guest@localhost:9999",  # Wrong port
            exchange="streamll_test",
        )
        sink.start()
        
        # Should not crash when RabbitMQ unavailable
        with streamll.configure(sinks=[sink]):
            with streamll.trace("breaker_test"):
                pass
                
        sink.stop()
        
        # Sink should have marked circuit as open
        assert sink._circuit_open
        
    @pytest.mark.asyncio
    async def test_rabbitmq_batch_processing(self, rabbitmq_cleanup):
        """Test batch event processing."""
        # Create sink
        sink = RabbitMQSink(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            routing_key="batch.events",
            batch_size=5,
        )
        sink.start()
        
        # Generate multiple events
        with streamll.configure(sinks=[sink]):
            for i in range(10):
                with streamll.trace(f"batch_op_{i}"):
                    pass
                    
        sink.flush()
        sink.stop()
        
        # Create consumer
        consumer = RabbitMQConsumer(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            exchange="streamll_test",
            queue="streamll_test_batch",
            routing_keys=["batch.events"],
        )
        
        await consumer.start()
        
        # Consume in batches
        batch = await consumer.consume_batch(max_events=5)
        assert len(batch) == 5
        
        # Consume more
        batch2 = await consumer.consume_batch(max_events=10)
        assert len(batch2) > 0
        
        await consumer.stop()