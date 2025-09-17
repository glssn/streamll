"""streamll - Production-ready streaming for DSPy applications."""

__version__ = "0.2.0-dev"

from streamll.context import configure, set_context, trace
from streamll.decorator import instrument
from streamll.models import Event
from streamll.sinks import TerminalSink

__all__ = [
    "instrument",
    "trace",
    "configure",
    "set_context",
    "Event",
    "TerminalSink",
]

try:
    from streamll.sinks import RedisSink

    __all__ += ["RedisSink"]
except ImportError:
    pass

try:
    from streamll.sinks import RabbitMQSink

    __all__ += ["RabbitMQSink"]
except ImportError:
    pass

try:
    from streamll.redis_consumer import RedisEventConsumer

    __all__ += ["RedisEventConsumer"]
except ImportError:
    pass

try:
    from streamll.rabbitmq_consumer import RabbitMQEventConsumer

    __all__ += ["RabbitMQEventConsumer"]
except ImportError:
    pass
