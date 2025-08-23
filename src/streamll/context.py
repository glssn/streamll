"""Context management for streamll event emission.

Handles execution context, sink management, and event routing.
"""

from contextvars import ContextVar
from typing import Any

from nanoid import generate

from streamll.models import StreamllEvent

# Global context for current execution
_execution_context: ContextVar[dict[str, Any] | None] = ContextVar("execution_context")

# Instance-based sink configuration
_module_sinks: dict[int, list[Any]] = {}  # module instance id -> sinks
_shared_sinks: list[Any] = []  # Shared sinks (like TerminalSink)
_global_event_filter: set[str] | None = None


def configure(sinks: list[Any] | None = None, event_filter: set[str] | None = None) -> None:
    """Configure shared streamll settings.

    Args:
        sinks: List of shared sink instances (like TerminalSink)
        event_filter: Set of event types to emit (None = all events)
    """
    global _shared_sinks, _global_event_filter

    if sinks is not None:
        # Validate sinks implement BaseSink interface
        from streamll.sinks.base import BaseSink

        for sink in sinks:
            if not isinstance(sink, BaseSink):
                raise TypeError(f"Sink {sink} must implement BaseSink interface")

        # Store shared sinks (TerminalSink, MetricsSink, etc)
        _shared_sinks.clear()
        _shared_sinks.extend(sinks)

        # Start shared sinks
        for sink in _shared_sinks:
            if not sink.is_running:
                sink.start()

    # Set event filter
    if event_filter is not None:
        _global_event_filter = event_filter


def configure_module(instance: Any, sinks: list[Any]) -> None:
    """Configure sinks for specific module instance.

    Args:
        instance: DSPy module instance
        sinks: List of sinks for this instance only
    """
    # Validate sinks implement BaseSink interface
    from streamll.sinks.base import BaseSink

    for sink in sinks:
        if not isinstance(sink, BaseSink):
            raise TypeError(f"Sink {sink} must implement BaseSink interface")

    # Store sinks keyed by instance id(instance)
    # Each instance gets isolated sink configuration
    # Enables same class used multiple times with different sinks
    _module_sinks[id(instance)] = sinks

    # Start the sinks
    for sink in sinks:
        if not sink.is_running:
            sink.start()


def get_execution_id() -> str:
    """Smart execution ID resolution.

    Returns:
        execution_id from DSPy context, streamll context, or new nanoid
    """
    # 1. Check if we're in a DSPy callback context
    try:
        from dspy.utils.callback import ACTIVE_CALL_ID

        dspy_id = ACTIVE_CALL_ID.get()
        if dspy_id:
            return dspy_id
    except (ImportError, AttributeError):
        # DSPy not available or no active call
        pass

    # 2. Check if we're in a streamll.trace() context
    ctx = _execution_context.get(None)
    if ctx and ctx.get("execution_id"):
        return ctx["execution_id"]

    # 3. Generate new ID for standalone calls
    return generate(size=12)


def emit(
    event_type: str,
    operation: str | None = None,
    data: dict[str, Any] | None = None,
    **kwargs,
) -> None:
    """Emit an event to configured sinks.

    Args:
        event_type: Type of event (start, end, token, error)
        operation: Optional operation name
        data: Event data payload
        **kwargs: Additional event fields
    """
    # Get current execution_id
    execution_id = get_execution_id()

    # Build StreamllEvent
    event = StreamllEvent(
        execution_id=execution_id,
        event_type=event_type,
        operation=operation,
        data=data or {},
        **kwargs,
    )

    # Route to all configured sinks (no module instance for manual emit)
    emit_event(event, module_instance=None)


def emit_event(event: StreamllEvent, module_instance: Any | None = None) -> None:
    """Emit a pre-built event to configured sinks.

    Args:
        event: StreamllEvent instance to emit
        module_instance: Optional module instance for sink routing
    """
    # Check event_filter
    if _global_event_filter is not None and event.event_type not in _global_event_filter:
        return

    # Get all relevant sinks
    all_sinks = []

    # Get module-specific sinks if instance provided
    if module_instance is not None:
        module_sinks = _module_sinks.get(id(module_instance), [])
        all_sinks.extend(module_sinks)

    # Get shared sinks (TerminalSink, MetricsSink)
    all_sinks.extend(_shared_sinks)

    # Send event to all relevant sinks
    for sink in all_sinks:
        try:
            if sink.is_running:
                sink.handle_event(event)
        except Exception as e:
            # Handle sink errors gracefully - don't crash the application
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Sink {type(sink).__name__} failed to handle event: {e}")


class StreamllContext:
    """Context manager for manual event tracing.

    Example:
        with streamll.trace("operation_name") as ctx:
            # Events emitted here will have this context
            result = do_work()
    """

    def __init__(
        self,
        operation: str,
        module_name: str | None = None,
        sinks: list[Any] | None = None,
        **metadata,
    ):
        """Initialize trace context.

        Args:
            operation: Name of operation being traced
            module_name: Optional module name override
            sinks: Additional sinks for this context only
            **metadata: Additional metadata to attach to events
        """
        self.operation = operation
        self.module_name = module_name or "manual"
        self.local_sinks = sinks or []
        self.metadata = metadata
        self.execution_id = None
        self.parent_context = None

    def __enter__(self) -> "StreamllContext":
        """Enter context - emit start event and set up context.

        Returns:
            Self for use in with statement
        """
        # Save parent context if exists
        # Generate or reuse execution_id
        # Set our context as active
        # Emit start event with operation
        # Return self for 'as' binding
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - emit end/error event and restore parent.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        # If exception, emit error event with details
        # Otherwise emit end event
        # Calculate duration if we tracked start time
        # Restore parent context
        # Don't suppress exceptions (return None)
        pass

    def emit(self, event_type: str, data: dict[str, Any] | None = None, **kwargs) -> None:
        """Emit event within this context.

        Args:
            event_type: Type of event
            data: Event data
            **kwargs: Additional event fields
        """
        # Use this context's execution_id
        # Add this context's metadata
        # Delegate to global emit
        pass


# Convenience function for creating trace context
def trace(operation: str, **kwargs) -> StreamllContext:
    """Create a trace context for manual instrumentation.

    Args:
        operation: Name of operation to trace
        **kwargs: Additional context parameters

    Returns:
        StreamllContext instance for use with 'with' statement
    """
    return StreamllContext(operation, **kwargs)
