"""DSPy callback integration for streamll.

Bridges DSPy's callback system with streamll event emission.
"""

from typing import Any

from dspy.utils.callback import BaseCallback

from streamll.context import emit_event
from streamll.models import StreamllEvent
from streamll.utils.version_tracker import ModuleVersionTracker


class StreamllDSPyCallback(BaseCallback):
    """DSPy callback that converts DSPy events to streamll events.

    This callback can be registered globally or per-module to automatically
    capture DSPy execution events.
    """

    def __init__(
        self,
        event_filter: set[str] | None = None,
        include_inputs: bool = True,
        include_outputs: bool = True,
        track_versions: bool = True,
        version_strategy: str = 'ast',
    ):
        """Initialize the callback.

        Args:
            event_filter: Set of event types to emit (None = all)
            include_inputs: Whether to include inputs in event data
            include_outputs: Whether to include outputs in event data
            track_versions: Whether to track module version hashes
            version_strategy: Strategy for version tracking ('ast', 'ast_with_deps', 'none')
        """
        self.event_filter = event_filter
        self.include_inputs = include_inputs
        self.include_outputs = include_outputs
        self._module_instance: Any | None = None  # Set by decorator
        self.track_versions = track_versions
        self._version_tracker = ModuleVersionTracker(strategy=version_strategy) if track_versions else None
        self._call_instances: dict[str, Any] = {}  # Map call_id to module instance

    def on_module_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Handle module forward() start.

        Args:
            call_id: DSPy's unique call identifier
            instance: The Module instance
            inputs: Input arguments to forward()
        """
        # Check event filter
        if self.event_filter and "start" not in self.event_filter:
            return

        # Build event data
        data = {}
        if self.include_inputs:
            data.update(inputs)

        # Store instance for use in on_module_end
        self._call_instances[call_id] = instance

        # Get module version if tracking is enabled
        module_version = None
        if self.track_versions and self._version_tracker:
            module_version = self._version_tracker.get_version(instance)

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id,  # Reuse DSPy's ID
            event_type="start",
            operation="module_forward",
            module_version=module_version,
            data=data,
            tags={"module_name": instance.__class__.__name__},
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance or instance)

    def on_module_end(
        self,
        call_id: str,
        outputs: Any | None,
        exception: Exception | None = None,
    ) -> None:
        """Handle module forward() end.

        Args:
            call_id: DSPy's unique call identifier
            outputs: Return value from forward()
            exception: Exception if one occurred
        """
        # Determine event type
        event_type = "error" if exception else "end"

        # Check event filter
        if self.event_filter and event_type not in self.event_filter:
            return

        # Build event data
        data = {}
        if exception:
            data["error"] = str(exception)
            data["error_type"] = exception.__class__.__name__
        elif outputs is not None and self.include_outputs:
            # Convert outputs to serializable format
            if hasattr(outputs, "model_dump"):
                data["outputs"] = outputs.model_dump()
            elif hasattr(outputs, "__dict__"):
                data["outputs"] = str(outputs)  # Safe fallback
            else:
                data["outputs"] = outputs

        # Retrieve the instance stored in on_module_start
        instance = self._call_instances.get(call_id, self._module_instance)

        # Get module version if tracking is enabled and we have the instance
        module_version = None
        if self.track_versions and self._version_tracker and instance:
            module_version = self._version_tracker.get_version(instance)

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id,
            event_type=event_type,
            operation="module_forward",
            module_version=module_version,
            data=data,
            tags={
                "module_name": instance.__class__.__name__ if instance else "unknown"
            },
        )

        # Emit the event
        emit_event(event, module_instance=instance)

        # Clean up the stored instance
        if call_id in self._call_instances:
            del self._call_instances[call_id]

    def on_lm_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Handle LM call start.

        Args:
            call_id: DSPy's unique call identifier
            instance: The LM instance
            inputs: Input arguments to LM
        """
        # Check event filter
        if self.event_filter and "start" not in self.event_filter:
            return

        # Build event data
        data = {}

        # Extract model info from instance
        if hasattr(instance, "model"):
            data["model"] = instance.model
            # Extract provider from model string (e.g., "gemini/gemini-2.5-flash" -> "gemini")
            provider = instance.model.split("/")[0] if "/" in instance.model else "unknown"
        else:
            provider = "unknown"

        # Include LM configuration
        if hasattr(instance, "temperature"):
            data["temperature"] = instance.temperature
        if hasattr(instance, "max_tokens"):
            data["max_tokens"] = instance.max_tokens
        if hasattr(instance, "top_p"):
            data["top_p"] = instance.top_p

        # Include inputs if allowed
        if self.include_inputs:
            # Extract prompt/messages from inputs
            if "prompt" in inputs:
                data["prompt"] = inputs["prompt"]
            if "messages" in inputs:
                data["messages"] = inputs["messages"]
            if "system" in inputs:
                data["system"] = inputs["system"]

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id,
            event_type="start",
            operation="llm_call",
            data=data,
            tags={"llm_provider": provider},
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance)

    def on_lm_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None,
    ) -> None:
        """Handle LM call end.

        Args:
            call_id: DSPy's unique call identifier
            outputs: LM response
            exception: Exception if one occurred
        """
        # Determine event type
        event_type = "error" if exception else "end"

        # Check event filter
        if self.event_filter and event_type not in self.event_filter:
            return

        # Build event data
        data = {}

        if exception:
            data["error"] = str(exception)
            data["error_type"] = exception.__class__.__name__
        elif outputs:
            # Include completion if allowed
            if self.include_outputs and "completion" in outputs:
                data["completion"] = outputs["completion"]

            # Always include usage stats if available (not sensitive)
            if "usage" in outputs:
                usage = outputs["usage"]
                if isinstance(usage, dict):
                    if "prompt_tokens" in usage:
                        data["prompt_tokens"] = usage["prompt_tokens"]
                    if "completion_tokens" in usage:
                        data["completion_tokens"] = usage["completion_tokens"]
                    if "total_tokens" in usage:
                        data["total_tokens"] = usage["total_tokens"]

            # Include model info if available
            if "model" in outputs:
                data["model"] = outputs["model"]

            # Include cache info if available
            if "cached" in outputs:
                data["cached"] = outputs["cached"]

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id, event_type=event_type, operation="llm_call", data=data, tags={}
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance)

    def on_lm_stream(
        self,
        call_id: str,
        token: str,
        token_index: int | None = None,
    ) -> None:
        """Handle streaming token from LM.

        Args:
            call_id: DSPy's unique call identifier
            token: The streamed token
            token_index: Optional index of token in stream
        """
        # Check event filter
        if self.event_filter and "token" not in self.event_filter:
            return

        # Build event data
        data = {
            "token": token,
        }

        if token_index is not None:
            data["token_index"] = token_index

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id, event_type="token", operation="llm_stream", data=data, tags={}
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance)

    def on_tool_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Handle tool invocation start.

        Args:
            call_id: DSPy's unique call identifier
            instance: The Tool instance
            inputs: Tool arguments
        """
        # Check event filter
        if self.event_filter and "start" not in self.event_filter:
            return

        # Build event data
        data = {}

        # Get tool name from instance
        if hasattr(instance, "name"):
            tool_name = instance.name
        elif hasattr(instance, "__class__"):
            tool_name = instance.__class__.__name__
        else:
            tool_name = "unknown_tool"

        data["tool_name"] = tool_name

        # Include tool description if available
        if hasattr(instance, "description"):
            data["description"] = instance.description

        # Include inputs if allowed
        if self.include_inputs:
            data["arguments"] = inputs

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id,
            event_type="start",
            operation="tool_call",
            data=data,
            tags={"tool": tool_name},
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance)

    def on_tool_end(
        self,
        call_id: str,
        outputs: dict[str, Any] | None,
        exception: Exception | None = None,
    ) -> None:
        """Handle tool invocation end.

        Args:
            call_id: DSPy's unique call identifier
            outputs: Tool results
            exception: Exception if one occurred
        """
        # Determine event type
        event_type = "error" if exception else "end"

        # Check event filter
        if self.event_filter and event_type not in self.event_filter:
            return

        # Build event data
        data = {}

        if exception:
            data["error"] = str(exception)
            data["error_type"] = exception.__class__.__name__
        elif outputs is not None and self.include_outputs:
            # Include tool outputs
            data["results"] = outputs

        # Build StreamllEvent
        event = StreamllEvent(
            execution_id=call_id, event_type=event_type, operation="tool_call", data=data, tags={}
        )

        # Emit the event
        emit_event(event, module_instance=self._module_instance)

    def on_adapter_format_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Handle adapter formatting start.

        Args:
            call_id: DSPy's unique call identifier
            instance: The Adapter instance
            inputs: Format arguments
        """
        # This is DSPy formatting prompts
        # Might want to track for debugging
        # Build event with operation = "adapter_format"
        # Emit if not filtered
        pass

    def on_adapter_parse_start(
        self,
        call_id: str,
        instance: Any,
        inputs: dict[str, Any],
    ) -> None:
        """Handle adapter parsing start.

        Args:
            call_id: DSPy's unique call identifier
            instance: The Adapter instance
            inputs: Parse arguments
        """
        # This is DSPy parsing LM outputs
        # Build event with operation = "adapter_parse"
        # Include raw output being parsed
        # Emit if not filtered
        pass
