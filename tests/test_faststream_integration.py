"""Tests for FastStream integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamll.brokers import create_broker
from streamll.event_consumer import EventConsumer
from streamll.models import StreamllEvent
from streamll.sinks.redis import RedisSink
from streamll.sinks.rabbitmq import RabbitMQSink


class TestBrokerFactory:
    """Test broker factory functionality."""

    def test_create_redis_broker(self):
        """Test creating Redis broker."""
        with patch("faststream.redis.RedisBroker") as mock_broker:
            broker = create_broker("redis://localhost:6379")
            # Currently using default JSON format for compatibility
            mock_broker.assert_called_once_with("redis://localhost:6379")
            assert broker is mock_broker.return_value

    def test_create_rabbitmq_broker(self):
        """Test creating RabbitMQ broker."""
        with patch("faststream.rabbit.RabbitBroker") as mock_broker:
            broker = create_broker("amqp://localhost:5672")
            mock_broker.assert_called_once_with("amqp://localhost:5672")
            assert broker is mock_broker.return_value

    def test_create_nats_broker(self):
        """Test creating NATS broker."""
        with patch("faststream.nats.NatsBroker") as mock_broker:
            broker = create_broker("nats://localhost:4222")
            mock_broker.assert_called_once_with("nats://localhost:4222")
            assert broker is mock_broker.return_value

    def test_unsupported_broker(self):
        """Test error on unsupported broker."""
        with pytest.raises(ValueError, match="Unsupported broker URL scheme"):
            create_broker("unknown://localhost")

    def test_missing_redis_dependency(self):
        """Test error when Redis dependencies not installed."""
        with patch("faststream.redis.RedisBroker", side_effect=ImportError):
            with pytest.raises(ImportError, match="Redis support not installed"):
                create_broker("redis://localhost:6379")


class TestRedisSink:
    """Test FastStream Redis sink."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        broker = MagicMock()
        broker.start = AsyncMock()
        broker.connect = AsyncMock()
        broker.close = AsyncMock()
        broker.stop = AsyncMock()
        broker.publish = AsyncMock()
        return broker

    def test_init(self):
        """Test sink initialization."""
        sink = RedisSink(
            redis_url="redis://localhost:6379",
            stream_key="test_stream",
        )

        # Test what actually matters - sink has the right properties and methods
        assert sink.stream_key == "test_stream"
        assert hasattr(sink, '_broker')
        assert hasattr(sink, 'handle_event')
        assert not sink.is_running  # Should start as stopped

    @pytest.mark.asyncio
    async def test_handle_event(self, mock_broker):
        """Test handling events."""
        # Create sink with mock broker
        with patch("streamll.sinks.redis.create_broker", return_value=mock_broker):
            sink = RedisSink(
                redis_url="redis://localhost:6379",
                stream_key="test_stream",
            )

            # Start sink
            sink.start()

            # Create test event
            event = StreamllEvent(
                execution_id="test", event_type="token", data={"token": "hello", "index": 0}
            )

            # Handle event (async now!)
            await sink.handle_event(event)

            # Stop sink
            sink.stop()


class TestRabbitMQSink:
    """Test RabbitMQ sink."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        broker = MagicMock()
        broker.start = AsyncMock()
        broker.connect = AsyncMock()
        broker.close = AsyncMock()
        broker.stop = AsyncMock()
        broker.publish = AsyncMock()
        return broker

    def test_init(self):
        """Test sink initialization."""
        sink = RabbitMQSink(
            rabbitmq_url="amqp://localhost:5672",
            queue="test_queue",
            exchange="test_exchange",
        )

        # Test what actually matters - sink has the right properties and methods
        assert sink.queue == "test_queue"
        assert sink.exchange == "test_exchange"
        assert hasattr(sink, '_broker')
        assert hasattr(sink, 'handle_event')
        assert not sink.is_running  # Should start as stopped

    @pytest.mark.asyncio
    async def test_handle_event(self, mock_broker):
        """Test handling events."""
        # Create sink with mock broker
        with patch("streamll.sinks.rabbitmq.create_broker", return_value=mock_broker):
            sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test_queue")

            # Start sink
            sink.start()

            # Create test event
            event = StreamllEvent(
                execution_id="test", event_type="error", data={"error": "Test error"}
            )

            # Handle event (async now!)
            await sink.handle_event(event)

            # Stop sink
            sink.stop()


class TestEventConsumer:
    """Test EventConsumer functionality."""

    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        broker = MagicMock()
        broker.start = AsyncMock()
        broker.close = AsyncMock()
        broker.subscriber = MagicMock()
        return broker

    def test_init_with_url(self):
        """Test consumer initialization with URL."""
        consumer = EventConsumer(broker_url="redis://localhost:6379", target="my_stream")

        assert consumer.broker_url == "redis://localhost:6379"
        assert consumer.target == "my_stream"

    def test_init_with_env_vars(self, monkeypatch):
        """Test consumer initialization with environment variables."""
        monkeypatch.setenv("STREAMLL_BROKER_URL", "amqp://localhost:5672")
        monkeypatch.setenv("STREAMLL_TARGET", "env_queue")

        consumer = EventConsumer()

        assert consumer.broker_url == "amqp://localhost:5672"
        assert consumer.target == "env_queue"

    def test_init_requires_broker_url(self):
        """Test that broker_url is required."""
        with pytest.raises(ValueError, match="broker_url required"):
            EventConsumer()

    def test_on_decorator_redis(self):
        """Test on decorator for Redis."""
        consumer = EventConsumer("redis://localhost:6379")

        # Register handler
        @consumer.on("token")
        async def handle_token(event: StreamllEvent):
            pass

        # Check handler was registered
        assert "token" in consumer._handlers
        assert len(consumer._handlers["token"]) == 1

    def test_on_decorator_rabbitmq(self):
        """Test on decorator for RabbitMQ."""
        consumer = EventConsumer("amqp://localhost:5672")

        # Register handler
        @consumer.on("error")
        async def handle_error(event: StreamllEvent):
            pass

        # Check handler was registered
        assert "error" in consumer._handlers
        assert len(consumer._handlers["error"]) == 1

    def test_multiple_handlers(self):
        """Test registering multiple handlers."""
        consumer = EventConsumer("redis://localhost:6379")

        # Register multiple handlers
        @consumer.on("token")
        async def handle_token1(event: StreamllEvent):
            pass

        @consumer.on("token")
        async def handle_token2(event: StreamllEvent):
            pass

        @consumer.on("error")
        async def handle_error(event: StreamllEvent):
            pass

        # Check handlers were registered
        assert len(consumer._handlers["token"]) == 2
        assert len(consumer._handlers["error"]) == 1
