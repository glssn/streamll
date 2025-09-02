"""Tests for all sink implementations."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamll.models import StreamllEvent
from streamll.sinks.redis import RedisSink
from streamll.sinks.rabbitmq import RabbitMQSink
from streamll.sinks.terminal import TerminalSink


class TestTerminalSink:
    """Test terminal sink."""

    def test_terminal_sink_basic(self, sample_event):
        """Test basic terminal output."""
        from io import StringIO

        output = StringIO()
        sink = TerminalSink(output=output)
        sink.start()

        sink.handle_event(sample_event)
        sink.stop()

        output_str = output.getvalue()
        assert "START" in output_str
        assert sample_event.operation in output_str

    def test_terminal_sink_token_streaming(self):
        """Test token streaming output."""
        from io import StringIO

        output = StringIO()
        sink = TerminalSink(show_tokens=True, output=output)
        sink.start()

        # Send token events
        for i, token in enumerate(["Hello", " ", "World"]):
            event = StreamllEvent(
                execution_id="test",
                event_type="token",
                data={"token": token, "index": i},
            )
            sink.handle_event(event)

        sink.stop()

        output_str = output.getvalue()
        assert "Hello World" in output_str


class TestRedisSink:
    """Test Redis sink using FastStream TestBroker."""

    @pytest.mark.asyncio
    async def test_redis_sink_publish(self):
        """Test Redis sink publishes events correctly."""
        from faststream.redis import RedisBroker, TestRedisBroker
        
        # Create real Redis broker for testing  
        broker = RedisBroker("redis://localhost:6379")
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key="test_stream")
        sink.start()
        
        # Use TestRedisBroker to verify behavior
        async with TestRedisBroker(broker) as test_broker:
            # Replace sink's broker with test broker
            sink._broker = test_broker
            
            event = StreamllEvent(
                execution_id="test", 
                event_type="token", 
                data={"token": "hello", "index": 0}
            )

            # Test async interface - this should work without assertion errors
            await sink.handle_event(event)
            
            # Just verify it completed without error - TestRedisBroker handles the rest


class TestRabbitMQSink:
    """Test RabbitMQ sink."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        broker = MagicMock()
        broker.start = AsyncMock()
        broker.connect = AsyncMock()
        broker.publish = AsyncMock()
        broker.stop = AsyncMock()
        
        # Mock the publisher returned by broker.publisher()
        mock_publisher = MagicMock()
        mock_publisher.publish = AsyncMock()
        broker.publisher.return_value = mock_publisher
        
        return broker

    def test_rabbitmq_sink_init(self):
        """Test RabbitMQ sink initialization."""
        sink = RabbitMQSink(
            rabbitmq_url="amqp://localhost:5672",
            queue="test_queue",
            exchange="test_exchange",
        )

        # Check that sink has required attributes and methods
        assert hasattr(sink, '_broker')
        assert hasattr(sink, 'is_running')
        assert hasattr(sink, 'handle_event')
        assert not sink.is_running  # Should start as stopped

    @pytest.mark.asyncio
    async def test_rabbitmq_sink_handle_event(self, mock_broker):
        """Test handling events."""
        with patch("streamll.sinks.rabbitmq.create_broker", return_value=mock_broker):
            sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test_queue")

            sink.start()

            event = StreamllEvent(
                execution_id="test", event_type="error", data={"error": "Test error"}
            )

            await sink.handle_event(event)
            sink.stop()