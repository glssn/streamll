"""streamll - Production-ready streaming for DSPy applications."""

__version__ = "0.1.0"

from streamll.context import configure, emit, emit_event, set_context, trace
from streamll.decorator import instrument
from streamll.event_consumer import EventConsumer
from streamll.models import Event
from streamll.sinks import TerminalSink
from streamll.streaming import create_streaming_wrapper

__all__ = [
    "Event",
    "configure",
    "emit",
    "emit_event",
    "set_context",
    "instrument",
    "trace",
    "create_streaming_wrapper",
    "EventConsumer",
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