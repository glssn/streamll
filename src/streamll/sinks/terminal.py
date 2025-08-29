"""Terminal sink for StreamLL events."""

import sys

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink


class TerminalSink(BaseSink):
    """Terminal sink that prints events with formatting."""

    def __init__(self, show_tokens: bool = True, output=None):
        """Initialize terminal sink.

        Args:
            show_tokens: Whether to show token events
            output: Optional file-like object for output (default: sys.stdout)
        """
        super().__init__(buffer_size=1, batch_size=1)  # No buffering
        self.show_tokens = show_tokens
        self.output = output or sys.stdout

    def start(self) -> None:
        """Start the sink."""
        super().start()

    def stop(self) -> None:
        """Stop the sink."""
        super().stop()

    def handle_event(self, event: StreamllEvent) -> None:
        """Print event to terminal."""
        # Skip token events if disabled
        if event.event_type == "token" and not self.show_tokens:
            return

        # Format timestamp
        ts = event.timestamp.strftime("%H:%M:%S")

        # Format based on event type
        if event.event_type == "token":
            token = event.data.get("token", "")
            self.output.write(token)
            self.output.flush()
        elif event.event_type == "start":
            self.output.write(f"[{ts}] START {event.operation or 'operation'}\n")
        elif event.event_type == "end":
            duration = event.data.get("duration", 0)
            self.output.write(f"[{ts}] END {event.operation or 'operation'} ({duration:.2f}s)\n")
        elif event.event_type == "error":
            error = event.data.get("error_message", "Unknown error")
            self.output.write(f"[{ts}] ERROR: {error}\n")
        else:
            self.output.write(f"[{ts}] {event.event_type.upper()}: {event.operation}\n")
