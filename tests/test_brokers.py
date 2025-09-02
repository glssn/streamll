"""Tests for FastStream broker factory."""

from unittest.mock import patch

import pytest

from streamll.brokers import create_broker


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