"""Context management for streamll event emission.

Handles execution context, sink management, and event routing.
"""

import time
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
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

    Automatically emits START and END/ERROR events, no code needed!

    Example:
        # Simplest usage - just wrap your code
        with streamll.trace("operation_name"):
            do_work()  # START and END events emitted automatically

        # With custom events
        with streamll.trace("operation_name") as ctx:
            result = do_work()
            ctx.emit("custom_metric", data={"size": len(result)})

    Events emitted:
        - On enter: START event with operation name and timestamp
        - On exit (success): END event with duration
        - On exit (exception): ERROR event with exception details
        - Custom: Any events you emit with ctx.emit()
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
        from streamll.models import generate_event_id

        # Generate execution_id for this trace context
        self.execution_id = generate_event_id()

        # Track start time for duration calculation
        self.start_time = time.time()

        # Save parent context if exists (for nested traces)
        self.parent_context = _execution_context.get(None)

        # Set this context as active
        _execution_context.set(
            {
                "execution_id": self.execution_id,
                "operation": self.operation,
                "metadata": self.metadata,
            }
        )

        # Start local sinks if provided
        for sink in self.local_sinks:
            if hasattr(sink, "is_running") and not sink.is_running:
                sink.start()

        # Emit START event
        start_event = StreamllEvent(
            event_id=generate_event_id(),
            execution_id=self.execution_id,
            timestamp=datetime.now(UTC),
            event_type="start",
            module_name=self.module_name,
            method_name=self.operation,
            operation=self.operation,
            data={**self.metadata, "stage": "start"},
        )

        # Emit to global sinks
        emit_event(start_event)

        # Also emit to local sinks
        for sink in self.local_sinks:
            if hasattr(sink, "is_running") and sink.is_running:
                try:
                    sink.handle_event(start_event)
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Local sink {type(sink).__name__} failed: {e}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - emit end/error event and restore parent.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        from streamll.models import generate_event_id

        # Calculate duration
        duration = time.time() - self.start_time

        if exc_type is not None:
            # Emit ERROR event if exception occurred
            error_event = StreamllEvent(
                event_id=generate_event_id(),
                execution_id=self.execution_id,
                timestamp=datetime.now(UTC),
                event_type="error",
                module_name=self.module_name,
                method_name=self.operation,
                operation=self.operation,
                data={
                    **self.metadata,
                    "duration_seconds": duration,
                    "stage": "error",
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val),
                    "traceback": "".join(traceback.format_tb(exc_tb)),
                },
            )
            emit_event(error_event)

            # Also emit to local sinks
            for sink in self.local_sinks:
                if hasattr(sink, "is_running") and sink.is_running:
                    try:
                        sink.handle_event(error_event)
                    except Exception as e:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(f"Local sink {type(sink).__name__} failed: {e}")
        else:
            # Emit END event for successful completion
            end_event = StreamllEvent(
                event_id=generate_event_id(),
                execution_id=self.execution_id,
                timestamp=datetime.now(UTC),
                event_type="end",
                module_name=self.module_name,
                method_name=self.operation,
                operation=self.operation,
                data={**self.metadata, "duration_seconds": duration, "stage": "end"},
            )
            emit_event(end_event)

            # Also emit to local sinks
            for sink in self.local_sinks:
                if hasattr(sink, "is_running") and sink.is_running:
                    try:
                        sink.handle_event(end_event)
                    except Exception as e:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(f"Local sink {type(sink).__name__} failed: {e}")

        # Restore parent context
        if self.parent_context:
            _execution_context.set(self.parent_context)
        else:
            _execution_context.set(None)

        # Don't suppress exceptions - return None

    def emit(self, event_type: str, data: dict[str, Any] | None = None, **kwargs) -> None:
        """Emit event within this context.

        Args:
            event_type: Type of event
            data: Event data
            **kwargs: Additional event fields
        """
        from streamll.models import generate_event_id

        # Merge provided data with metadata and kwargs
        event_data = {**self.metadata}
        if data:
            event_data.update(data)
        event_data.update(kwargs)

        # Create event using this context's execution_id
        event = StreamllEvent(
            event_id=generate_event_id(),
            execution_id=self.execution_id,
            timestamp=datetime.now(UTC),
            event_type=event_type,
            module_name=self.module_name,
            method_name=self.operation,
            operation=self.operation,
            data=event_data,
        )

        # Emit to both local sinks and global sinks
        emit_event(event)

        # Also emit to local sinks if they exist
        for sink in self.local_sinks:
            if hasattr(sink, "is_running") and sink.is_running:
                try:
                    sink.handle_event(event)
                except Exception as e:
                    # Log but don't crash
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(f"Local sink {type(sink).__name__} failed: {e}")


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
