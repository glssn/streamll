"""streamll - Production-ready streaming for DSPy applications."""

__version__ = "0.1.0"

from streamll.models import StreamllEvent, generate_event_id

# Core is always in __all__
__all__ = [
    # Core events
    "StreamllEvent",
    "generate_event_id",
]

try:
    # Try to import producer functionality
    from streamll.context import configure, emit, emit_event, trace
    from streamll.decorator import instrument
    from streamll.streaming import create_streaming_wrapper

    # Add to exports if available
    __all__.extend(
        [
            "configure",
            "emit",
            "emit_event",
            "instrument",
            "trace",
            "create_streaming_wrapper",
        ]
    )

    # Mark producer as available
    _producer_available = True

except ImportError:
    _producer_available = False

    # Create placeholder functions with helpful errors
    def _producer_not_installed(*args, **kwargs):
        raise ImportError(
            "Producer functionality not installed. Install with: pip install streamll[producer]"
        )

    configure = _producer_not_installed  # type: ignore[assignment]
    instrument = _producer_not_installed  # type: ignore[assignment]
    emit = _producer_not_installed  # type: ignore[assignment]
    emit_event = _producer_not_installed  # type: ignore[assignment]
    trace = _producer_not_installed  # type: ignore[assignment]
    create_streaming_wrapper = _producer_not_installed  # type: ignore[assignment]

try:
    from streamll.event_consumer import EventConsumer

    __all__.extend(
        [
            "EventConsumer",
        ]
    )

    _consumer_available = True

except ImportError:
    _consumer_available = False

    # Placeholder for consumer classes
    class EventConsumer:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Consumer functionality not installed. "
                "Install with: pip install streamll[redis-consumer]"
            )


from streamll.sinks import TerminalSink  # noqa: F401

__all__.extend(["TerminalSink"])

# Redis sink
try:
    from streamll.sinks import RedisSink  # type: ignore[possibly-unbound-import]

    __all__.append("RedisSink")
except ImportError:
    # Type stub for when Redis dependencies aren't installed
    class RedisSink:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Redis sink not installed. Install with: pip install streamll[redis-producer]"
            )


# RabbitMQ sink
try:
    from streamll.sinks import RabbitMQSink  # type: ignore[possibly-unbound-import]

    __all__.append("RabbitMQSink")
except ImportError:
    # Type stub for when RabbitMQ dependencies aren't installed
    class RabbitMQSink:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "RabbitMQ sink not installed. Install with: pip install streamll[rabbitmq-producer]"
            )


def get_installed_features():
    """Get list of installed streamll features.

    Returns:
        Dict of feature -> bool indicating what's installed
    """
    return {
        "core": True,  # Always available
        "producer": _producer_available,
        "consumer": _consumer_available,
        "redis": "RedisSink" in __all__ and not isinstance(RedisSink, type),
        "rabbitmq": "RabbitMQSink" in __all__ and not isinstance(RabbitMQSink, type),
    }


try:
    from streamll.models import StreamllEvent as _OldStreamllEvent

    # Alias for backward compat
    if "StreamllEvent" not in locals():
        StreamllEvent = _OldStreamllEvent
except ImportError:
    pass
