from unittest.mock import MagicMock, Mock, patch


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
    def test_init(self):
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key="test_stream")
        assert sink.stream_key == "test_stream"
        assert sink.redis_url == "redis://localhost:6379"
        assert not sink.is_running
        assert sink.max_stream_length == 10000

    def test_handle_event_with_mock(self):
        mock_redis = MagicMock()
        mock_pool = MagicMock()

        with (
            patch("streamll.sinks.redis.redis.ConnectionPool.from_url", return_value=mock_pool),
            patch("streamll.sinks.redis.redis.Redis", return_value=mock_redis),
        ):
            sink = RedisSink(redis_url="redis://localhost:6379", stream_key="test")
            sink.start()

            event = Event(execution_id="test", event_type="test_event", data={"key": "value"})
            sink.handle_event(event)

            # Verify Redis XADD was called with correct parameters
            mock_redis.xadd.assert_called_once()
            call_args = mock_redis.xadd.call_args
            assert call_args[1]["name"] == "test"
            assert call_args[1]["maxlen"] == 10000
            assert call_args[1]["approximate"] is True

            sink.stop()

    def test_start_stop_lifecycle(self):
        with (
            patch("streamll.sinks.redis.redis.ConnectionPool.from_url") as mock_pool_from_url,
            patch("streamll.sinks.redis.redis.Redis") as mock_redis_class,
        ):
            mock_pool = MagicMock()
            mock_redis = MagicMock()
            mock_pool_from_url.return_value = mock_pool
            mock_redis_class.return_value = mock_redis

            sink = RedisSink()
            assert not sink.is_running

            sink.start()
            assert sink.is_running
            mock_pool_from_url.assert_called_once_with("redis://localhost:6379")
            mock_redis_class.assert_called_once_with(connection_pool=mock_pool)

            sink.stop()
            assert not sink.is_running
            mock_pool.disconnect.assert_called_once()

    def test_handle_event_not_running(self):
        sink = RedisSink()
        event = Event(execution_id="test", event_type="test")

        # Should return early without errors
        sink.handle_event(event)
        assert not sink.is_running


class TestRabbitMQSink:
    def test_init(self):
        sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test_queue")

        assert sink.queue == "test_queue"
        assert sink.rabbitmq_url == "amqp://localhost:5672"
        assert not sink.is_running

    def test_handle_event_with_mock(self):
        mock_connection = Mock()
        mock_channel = Mock()
        mock_connection.is_closed = False
        mock_connection.channel.return_value = mock_channel

        with patch("streamll.sinks.rabbitmq.pika.BlockingConnection", return_value=mock_connection):
            sink = RabbitMQSink(rabbitmq_url="amqp://localhost:5672", queue="test")
            sink.start()

            event = Event(execution_id="test", event_type="error", data={"error": "test"})
            sink.handle_event(event)

            mock_channel.basic_publish.assert_called_once()
            sink.stop()
