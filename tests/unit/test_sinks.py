from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamll.models import Event
from streamll.sinks.rabbitmq import RabbitMQSink
from streamll.sinks.redis import RedisSink
from streamll.sinks.terminal import TerminalSink


class TestTerminalSink:
    def test_terminal_sink_handles_events(self, capsys):
        sink = TerminalSink()
        sink.start()

        event = Event(execution_id="test", event_type="test", data={"message": "test"})
        sink.handle_event(event)

        captured = capsys.readouterr()
        assert "TEST" in captured.out  # Terminal sink uppercases event types


class TestRedisSink:
    def test_init_with_mock_broker(self):
        with patch("streamll.sinks.redis.RedisBroker") as mock_broker_class:
            mock_broker_class.return_value = MagicMock()
            sink = RedisSink(redis_url="redis://localhost:6379", stream_key="test")

            assert sink.stream_key == "test"
            assert hasattr(sink, "broker")
            assert not sink.is_running

    @pytest.mark.asyncio
    async def test_handle_event_with_mock(self):
        mock_broker = MagicMock()
        mock_broker.connect = AsyncMock()
        mock_broker.publish = AsyncMock()
        mock_broker.stop = AsyncMock()

        with patch("streamll.sinks.redis.RedisBroker", return_value=mock_broker):
            sink = RedisSink(redis_url="redis://localhost:6379", stream_key="test")
            await sink.start()

            event = Event(execution_id="test", event_type="test")
            await sink.handle_event(event)

            mock_broker.publish.assert_called_once()
            await sink.stop()


class TestRabbitMQSink:
    def test_init_with_mock_broker(self):
        with patch("streamll.sinks.rabbitmq.RabbitBroker") as mock_broker_class:
            mock_broker_class.return_value = MagicMock()
            sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test_queue")

            assert sink.queue == "test_queue"
            assert hasattr(sink, "broker")
            assert not sink.is_running

    @pytest.mark.asyncio
    async def test_handle_event_with_mock(self):
        mock_broker = MagicMock()
        mock_broker.connect = AsyncMock()
        mock_broker.publish = AsyncMock()
        mock_broker.stop = AsyncMock()

        with patch("streamll.sinks.rabbitmq.RabbitBroker", return_value=mock_broker):
            sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test")
            await sink.start()

            event = Event(execution_id="test", event_type="error", data={"error": "test"})
            await sink.handle_event(event)

            mock_broker.publish.assert_called_once_with(event, queue="test")
            await sink.stop()
