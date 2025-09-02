"""Minimal DSPy callback for streamll integration."""

import time
from typing import Any

from dspy.utils.callback import BaseCallback

from streamll.context import emit_event
from streamll.models import StreamllEvent


class StreamllDSPyCallback(BaseCallback):
    """Bridge between DSPy callbacks and streamll events."""

    def __init__(self, include_inputs: bool = True, include_outputs: bool = True):
        self.include_inputs = include_inputs
        self.include_outputs = include_outputs
        self._module_instance = None  # Set by decorator
        self._call_start_times = {}  # Track start times by call_id

    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        """Emit start event when module.forward() is called."""
        # Track start time
        self._call_start_times[call_id] = time.time()

        data = {}
        if self.include_inputs:
            data.update(inputs)

        event = StreamllEvent(
            execution_id=call_id,
            event_type="start",
            operation="forward",
            data=data,
            tags={"module": instance.__class__.__name__},
        )
        emit_event(event, module_instance=self._module_instance or instance)

    def on_module_end(
        self, call_id: str, outputs: Any | None, exception: Exception | None = None
    ) -> None:
        """Emit end/error event when module.forward() completes."""
        # Calculate duration
        start_time = self._call_start_times.get(call_id)
        duration = time.time() - start_time if start_time else 0

        # Clean up start time
        self._call_start_times.pop(call_id, None)

        if exception:
            event = StreamllEvent(
                execution_id=call_id,
                event_type="error",
                operation="forward",
                data={
                    "error": str(exception),
                    "error_type": exception.__class__.__name__,
                    "duration": duration,
                },
            )
        else:
            data = {"duration": duration}
            if self.include_outputs and outputs is not None:
                # Simple serialization
                if hasattr(outputs, "model_dump"):
                    data["outputs"] = outputs.model_dump()
                elif isinstance(outputs, dict):
                    data["outputs"] = outputs
                else:
                    data["outputs"] = str(outputs)

            event = StreamllEvent(
                execution_id=call_id, event_type="end", operation="forward", data=data
            )

        emit_event(event, module_instance=self._module_instance)

    def on_lm_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        """Emit event when LM is called."""
        event = StreamllEvent(
            execution_id=call_id,
            event_type="llm_start",
            operation="generate",
            data=inputs if self.include_inputs else {},
        )
        emit_event(event, module_instance=self._module_instance)

    def on_lm_end(
        self, call_id: str, outputs: Any | None, exception: Exception | None = None
    ) -> None:
        """Emit event when LM completes."""
        if exception:
            return  # Already handled by on_module_end

        data = {}
        if self.include_outputs and outputs:
            data["response"] = str(outputs)

        event = StreamllEvent(
            execution_id=call_id, event_type="llm_end", operation="generate", data=data
        )
        emit_event(event, module_instance=self._module_instance)

    def on_lm_stream(self, call_id: str, token: str, token_index: int) -> None:
        """Emit token event during streaming."""
        event = StreamllEvent(
            execution_id=call_id,
            event_type="token",
            operation="stream",
            data={"token": token, "index": token_index},
        )
        emit_event(event, module_instance=self._module_instance)
