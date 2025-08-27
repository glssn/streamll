"""Decorator for instrumenting DSPy modules with streamll.

Provides @streamll.instrument decorator for automatic event emission.
"""

import functools
from collections.abc import Callable
from typing import Any

import dspy

from streamll.dspy_callback import StreamllDSPyCallback


def instrument(  # noqa: C901
    cls: type[dspy.Module] | None = None,
    *,
    sinks: list[Any] | None = None,
    include_inputs: bool = True,
    include_outputs: bool = True,
    stream_fields: list[str] | None = None,
) -> Callable | type[dspy.Module]:
    """Decorator to instrument DSPy modules with streamll events.

    Can be used as @instrument or @instrument(...) with parameters.

    Args:
        cls: The class being decorated (when used without parens)
        sinks: Additional sinks for this module only
        include_inputs: Whether to include inputs in events
        include_outputs: Whether to include outputs in events
        stream_fields: Optional list of string field names to stream token-by-token.
                      When specified, TokenEvents will be emitted for these fields.

    Returns:
        Decorated class or decorator function

    Example:
        @streamll.instrument
        class MyModule(dspy.Module):
            def forward(self, x):
                return self.predict(x)

        @streamll.instrument(include_outputs=False)
        class SecureModule(dspy.Module):
            def forward(self, query):
                return self.retrieve(query)
    """

    def decorator(cls: type[dspy.Module]) -> type[dspy.Module]:
        """Inner decorator that modifies the class.

        Args:
            cls: DSPy Module class to instrument

        Returns:
            Instrumented class
        """
        # Validate that this is a DSPy Module
        if not issubclass(cls, dspy.Module):
            raise TypeError(
                f"@streamll.instrument can only be applied to dspy.Module subclasses, got {cls}"
            )

        # Check if already instrumented
        if hasattr(cls, "_streamll_instrumented"):
            raise ValueError(
                f"Class {cls.__name__} is already instrumented with @streamll.instrument"
            )

        # Mark as instrumented (use setattr to avoid type checker issues)
        setattr(cls, "_streamll_instrumented", True)

        # Save original __init__
        original_init = cls.__init__

        @functools.wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            """Wrapped __init__ that adds streamll callback.

            Args:
                self: Instance being initialized
                *args: Positional arguments to original __init__
                **kwargs: Keyword arguments to original __init__
            """
            # Call original __init__ first
            # This ensures self.callbacks exists (DSPy creates it)
            original_init(self, *args, **kwargs)

            # Create streamll callback with decorator parameters
            streamll_callback = StreamllDSPyCallback(
                include_inputs=include_inputs,
                include_outputs=include_outputs,
            )

            # Add to module's callbacks list
            # DSPy will automatically call it
            if not hasattr(self, "callbacks"):
                self.callbacks = []
            self.callbacks.append(streamll_callback)

            # Auto-configure shared TerminalSink if no sinks configured
            from streamll.context import _shared_sinks, configure, configure_module
            from streamll.sinks import TerminalSink

            if not _shared_sinks and not sinks:
                configure(sinks=[TerminalSink()], permanent=True)

            # Configure module-specific sinks if provided
            if sinks:
                # Validate sinks before configuring
                from streamll.sinks.base import BaseSink

                for sink in sinks:
                    if not isinstance(sink, BaseSink):
                        raise TypeError(
                            f"All sinks must implement BaseSink interface, got {type(sink)}"
                        )
                configure_module(self, sinks)

            # Store instance reference for sink routing
            streamll_callback._module_instance = self

            # Store streaming configuration
            self._streamll_stream_fields = stream_fields or []

            # Wrap forward method if streaming enabled
            if stream_fields and hasattr(self, "forward"):
                from streamll.streaming import wrap_with_streaming

                original_forward = self.forward
                self.forward = wrap_with_streaming(original_forward, self, stream_fields)

        # Replace __init__ with wrapped version
        cls.__init__ = wrapped_init

        return cls

    # Handle both @instrument and @instrument(...) syntax
    if cls is None:
        # Called with arguments: @instrument(...)
        return decorator
    else:
        # Called without arguments: @instrument
        return decorator(cls)
