"""Sink implementations for streamll event output."""

from streamll.sinks.base import BaseSink
from streamll.sinks.terminal import TerminalSink

__all__ = [
    "BaseSink",
    "TerminalSink",
]

# Optional Redis sink if dependencies available
try:
    from streamll.sinks.redis import RedisSink  # noqa: F401

    __all__.append("RedisSink")
except ImportError:
    pass  # Redis dependencies not installed

# Optional RabbitMQ sink if dependencies available
try:
    from streamll.sinks.rabbitmq import RabbitMQSink  # noqa: F401

    __all__.append("RabbitMQSink")
except ImportError:
    pass  # RabbitMQ dependencies not installed
