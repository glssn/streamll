import logging
import time
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from nanoid import generate

from streamll.models import StreamllEvent, generate_event_id

logger = logging.getLogger(__name__)

_execution_context: ContextVar[dict[str, Any] | None] = ContextVar("execution_context")
_conversation_context: ContextVar[dict[str, Any] | None] = ContextVar("conversation_context")
_module_sinks: dict[int, list[Any]] = {}
_shared_sinks: list[Any] = []
_global_event_filter: set[str] | None = None


def _validate_and_start_sinks(sinks: list[Any]) -> None:
    for sink in sinks:
        if not hasattr(sink, "handle_event"):
            raise TypeError(f"Sink {sink} must have handle_event method")
        if hasattr(sink, "is_running") and not sink.is_running:
            if hasattr(sink, "start"):
                result = sink.start()
                if hasattr(result, "__await__"):
                    import asyncio

                    try:
                        asyncio.get_running_loop()
                        logger.warning(
                            f"Cannot start async sink {type(sink).__name__} from sync context"
                        )
                    except RuntimeError:
                        asyncio.run(result)


def _emit_to_sinks(event: StreamllEvent, sinks: list[Any]) -> None:
    import asyncio
    import inspect

    for sink in sinks:
        if hasattr(sink, "is_running") and sink.is_running:
            try:
                result = sink.handle_event(event)
                if inspect.iscoroutine(result):
                    try:
                        try:
                            asyncio.get_running_loop()
                            import concurrent.futures

                            def run_in_thread():
                                return asyncio.run(result)

                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(run_in_thread)
                                future.result(timeout=5.0)

                        except RuntimeError:
                            asyncio.run(result)
                    except Exception as e:
                        logger.warning(f"Async sink {type(sink).__name__} failed: {e}")
            except Exception as e:
                logger.warning(f"Sink {type(sink).__name__} failed: {e}")


class ConfigurationContext:
    def __init__(self, sinks: list[Any] | None = None, event_filter: set[str] | None = None):
        self.sinks = sinks or []
        self.event_filter = event_filter
        self.previous_sinks = []
        self.previous_filter = None

    def __enter__(self):
        global _shared_sinks, _global_event_filter
        self.previous_sinks = _shared_sinks.copy()
        self.previous_filter = _global_event_filter

        if self.sinks:
            _validate_and_start_sinks(self.sinks)
            _shared_sinks.clear()
            _shared_sinks.extend(self.sinks)

        if self.event_filter is not None:
            _global_event_filter = self.event_filter

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _shared_sinks, _global_event_filter

        for sink in _shared_sinks:
            if sink.is_running:
                sink.stop()

        _shared_sinks.clear()
        _shared_sinks.extend(self.previous_sinks)
        _global_event_filter = self.previous_filter

        for sink in _shared_sinks:
            if not sink.is_running:
                sink.start()


def configure(
    sinks: list[Any] | None = None, event_filter: set[str] | None = None, permanent: bool = False
) -> ConfigurationContext:
    global _shared_sinks, _global_event_filter

    if permanent:
        if sinks is not None:
            _validate_and_start_sinks(sinks)
            _shared_sinks.clear()
            _shared_sinks.extend(sinks)
        if event_filter is not None:
            _global_event_filter = event_filter

    return ConfigurationContext(sinks, event_filter)


def configure_module(instance: Any, sinks: list[Any]) -> None:
    _validate_and_start_sinks(sinks)
    _module_sinks[id(instance)] = sinks


def set_context(**context: Any) -> None:
    _conversation_context.set(context)


def get_conversation_context() -> dict[str, Any]:
    try:
        return _conversation_context.get() or {}
    except LookupError:
        return {}


def get_execution_id() -> str:
    try:
        from dspy.utils.callback import ACTIVE_CALL_ID

        if dspy_id := ACTIVE_CALL_ID.get():
            return dspy_id
    except (ImportError, AttributeError):
        pass

    ctx = _execution_context.get(None)
    if ctx and ctx.get("execution_id"):
        return ctx["execution_id"]

    return generate(size=12)


def emit(
    event_type: str,
    operation: str | None = None,
    data: dict[str, Any] | None = None,
    **kwargs,
) -> None:
    event = StreamllEvent(
        execution_id=get_execution_id(),
        event_type=event_type,
        operation=operation,
        data=data or {},
        **kwargs,
    )
    emit_event(event, module_instance=None)


def emit_event(event: StreamllEvent, module_instance: Any | None = None) -> None:
    if _global_event_filter and event.event_type not in _global_event_filter:
        return

    all_sinks = []
    if module_instance:
        all_sinks.extend(_module_sinks.get(id(module_instance), []))
    all_sinks.extend(_shared_sinks)

    _emit_to_sinks(event, all_sinks)


class StreamllContext:
    def __init__(
        self,
        operation: str,
        module_name: str | None = None,
        sinks: list[Any] | None = None,
        **metadata,
    ):
        self.operation = operation
        self.module_name = module_name or "manual"
        self.local_sinks = sinks or []
        self.metadata = metadata
        self.execution_id = None
        self.start_time = None
        self.parent_context = None

    def __enter__(self) -> "StreamllContext":
        self.execution_id = generate_event_id()
        self.start_time = time.time()

        self.parent_context = _execution_context.get(None)
        _execution_context.set(
            {
                "execution_id": self.execution_id,
                "operation": self.operation,
                "metadata": self.metadata,
            }
        )

        for sink in self.local_sinks:
            if hasattr(sink, "is_running") and not sink.is_running:
                sink.start()

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

        emit_event(start_event)
        _emit_to_sinks(start_event, self.local_sinks)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = time.time() - self.start_time

        event_data = {
            **self.metadata,
            "duration_seconds": duration,
            "stage": "error" if exc_type else "end",
        }

        if exc_type:
            event_data.update(
                {
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val),
                    "traceback": "".join(traceback.format_tb(exc_tb)),
                }
            )

        event = StreamllEvent(
            event_id=generate_event_id(),
            execution_id=self.execution_id,
            timestamp=datetime.now(UTC),
            event_type="error" if exc_type else "end",
            module_name=self.module_name,
            method_name=self.operation,
            operation=self.operation,
            data=event_data,
        )

        emit_event(event)
        _emit_to_sinks(event, self.local_sinks)

        _execution_context.set(self.parent_context)

    def emit(self, event_type: str, data: dict[str, Any] | None = None, **kwargs) -> None:
        context_data = get_conversation_context()
        emit(
            event_type=event_type,
            operation=self.operation,
            module_name=self.module_name,
            method_name=self.operation,
            data={**context_data, **self.metadata, **(data or {}), **kwargs},
        )


def trace(operation: str, **kwargs) -> StreamllContext:
    return StreamllContext(operation, **kwargs)
