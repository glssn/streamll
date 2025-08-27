"""StreamLL - Production Streaming Infrastructure for DSPy.

Transform black-box LLM pipelines into observable, real-time systems.
"""

__version__ = "0.1.0"

# =============================================================================
# CORE IMPORTS (Always available - zero dependencies)
# =============================================================================
from streamll.models import StreamllEvent, generate_event_id

# Core is always in __all__
__all__ = [
    # Core events
    "StreamllEvent",
    "generate_event_id",
]

# =============================================================================
# PRODUCER IMPORTS (Requires: pip install streamll[producer])
# =============================================================================
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

    # Explicitly shadow functions with error handlers (type: ignore to suppress warnings)
    configure = _producer_not_installed  # type: ignore[assignment]
    instrument = _producer_not_installed  # type: ignore[assignment]
    emit = _producer_not_installed  # type: ignore[assignment]
    emit_event = _producer_not_installed  # type: ignore[assignment]
    trace = _producer_not_installed  # type: ignore[assignment]
    create_streaming_wrapper = _producer_not_installed  # type: ignore[assignment]

# =============================================================================
# CONSUMER IMPORTS (Requires: pip install streamll[consumer])
# =============================================================================
try:
    from streamll.consumer import BaseConsumer, RedisStreamConsumer

    __all__.extend(
        [
            "BaseConsumer",
            "RedisStreamConsumer",
        ]
    )

    _consumer_available = True

except ImportError:
    _consumer_available = False

    # Placeholder for consumer classes
    class BaseConsumer:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Consumer functionality not installed. "
                "Install with: pip install streamll[redis-consumer]"
            )

    RedisStreamConsumer = BaseConsumer  # type: ignore[assignment]

# =============================================================================
# SINK IMPORTS (Conditional based on installed extras)
# =============================================================================

# Terminal sinks (always available if producer is installed)
if _producer_available:
    try:
        from streamll.sinks import TerminalSink  # noqa: F401

        __all__.extend(["TerminalSink"])
    except ImportError:
        pass

# Redis sink
try:
    from streamll.sinks import RedisSink

    __all__.append("RedisSink")
except ImportError:

    class RedisSink:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Redis sink not installed. Install with: pip install streamll[redis-producer]"
            )


# RabbitMQ sink
try:
    from streamll.sinks import RabbitMQSink

    __all__.append("RabbitMQSink")
except ImportError:

    class RabbitMQSink:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "RabbitMQ sink not installed. Install with: pip install streamll[rabbitmq-producer]"
            )


# =============================================================================
# COMPATIBILITY AND HELPERS
# =============================================================================


def get_installed_features():
    """Get list of installed StreamLL features.

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


# For backward compatibility with old imports
# (even though there are no users yet, good practice)
try:
    from streamll.models import StreamllEvent as _OldStreamllEvent

    # Alias for backward compat
    if "StreamllEvent" not in locals():
        StreamllEvent = _OldStreamllEvent
except ImportError:
    pass
