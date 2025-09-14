import time
from typing import Any

from dspy.utils.callback import BaseCallback

from streamll.context import emit_event, get_conversation_context
from streamll.models import StreamllEvent


class StreamllDSPyCallback(BaseCallback):
    def __init__(self, include_inputs: bool = True, include_outputs: bool = True):
        self.include_inputs = include_inputs
        self.include_outputs = include_outputs
        self._module_instance = None
        self._call_start_times = {}

    def on_module_start(self, call_id: str, instance: Any, inputs: dict[str, Any]) -> None:
        self._call_start_times[call_id] = time.time()

        data = get_conversation_context()
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
        start_time = self._call_start_times.get(call_id)
        duration = time.time() - start_time if start_time else 0

        self._call_start_times.pop(call_id, None)

        if exception:
            data = get_conversation_context()
            data.update(
                {
                    "error": str(exception),
                    "error_type": exception.__class__.__name__,
                    "duration": duration,
                }
            )
            event = StreamllEvent(
                execution_id=call_id,
                event_type="error",
                operation="forward",
                data=data,
            )
        else:
            data = get_conversation_context()
            data["duration"] = duration
            if self.include_outputs and outputs is not None:
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
        data = get_conversation_context()
        if self.include_inputs:
            data.update(inputs)
        event = StreamllEvent(
            execution_id=call_id,
            event_type="llm_start",
            operation="generate",
            data=data,
        )
        emit_event(event, module_instance=self._module_instance)

    def on_lm_end(
        self, call_id: str, outputs: Any | None, exception: Exception | None = None
    ) -> None:
        if exception:
            return

        data = get_conversation_context()
        if self.include_outputs and outputs:
            data["response"] = str(outputs)

        event = StreamllEvent(
            execution_id=call_id, event_type="llm_end", operation="generate", data=data
        )
        emit_event(event, module_instance=self._module_instance)

    def on_lm_stream(self, call_id: str, token: str, token_index: int) -> None:
        data = get_conversation_context()
        data.update({"token": token, "index": token_index})
        event = StreamllEvent(
            execution_id=call_id,
            event_type="token",
            operation="stream",
            data=data,
        )
        emit_event(event, module_instance=self._module_instance)
