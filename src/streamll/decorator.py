import functools
from collections.abc import Callable
from typing import Any

import dspy

from streamll.dspy_callback import StreamllDSPyCallback


def instrument(
    cls: type[dspy.Module] | None = None,
    *,
    sinks: list[Any] | None = None,
    include_inputs: bool = True,
    include_outputs: bool = True,
    stream_fields: list[str] | None = None,
) -> Callable | type[dspy.Module]:
    def decorator(cls: type[dspy.Module]) -> type[dspy.Module]:
        if not issubclass(cls, dspy.Module):
            raise TypeError(
                f"@streamll.instrument can only be applied to dspy.Module subclasses, got {cls}"
            )

        if hasattr(cls, "_streamll_instrumented"):
            raise ValueError(
                f"Class {cls.__name__} is already instrumented with @streamll.instrument"
            )

        cls._streamll_instrumented = True  # type: ignore[attr-defined]

        original_init = cls.__init__

        @functools.wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            streamll_callback = StreamllDSPyCallback(
                include_inputs=include_inputs,
                include_outputs=include_outputs,
            )

            if not hasattr(self, "callbacks"):
                self.callbacks = []
            self.callbacks.append(streamll_callback)

            from streamll.context import _shared_sinks, configure, configure_module
            from streamll.sinks import TerminalSink

            if not _shared_sinks and not sinks:
                configure(sinks=[TerminalSink()], permanent=True)

            if sinks:
                for sink in sinks:
                    if not hasattr(sink, "handle_event"):
                        raise TypeError(
                            f"All sinks must have handle_event method, got {type(sink)}"
                        )
                configure_module(self, sinks)

            streamll_callback._module_instance = self
            self._streamll_stream_fields = stream_fields or []

            if stream_fields and hasattr(self, "forward"):
                from streamll.streaming import wrap_with_streaming

                original_forward = self.forward
                self.forward = wrap_with_streaming(original_forward, self, stream_fields)

        cls.__init__ = wrapped_init

        return cls

    if cls is None:
        return decorator
    else:
        return decorator(cls)
