import sys
from io import TextIOWrapper
from typing import TextIO

from streamll.models import Event


class TerminalSink:
    def __init__(self, show_tokens: bool = True, show_data: bool = True, output: TextIO | TextIOWrapper | None = None):
        self.show_tokens = show_tokens
        self.show_data = show_data
        self.output = output or sys.stdout
        self.is_running = False
        self._last_was_token = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def handle_event(self, event: Event) -> None:
        if event.event_type == "token" and not self.show_tokens:
            return

        ts = event.timestamp.strftime("%H:%M:%S")

        if event.event_type == "token":
            token = event.data.get("token", "")
            self.output.write(token)
            self.output.flush()
            self._last_was_token = True
        else:
            if self._last_was_token:
                self.output.write("\n")

            if event.event_type == "start":
                self.output.write(f"[{ts}] START {event.operation or 'operation'}")
                if self.show_data and "inputs" in event.data:
                    self.output.write(f" | inputs: {event.data['inputs']}")
                self._write_metadata(event)
                self.output.write("\n")
            elif event.event_type == "end":
                duration = event.data.get("duration_seconds", 0)
                self.output.write(f"[{ts}] END {event.operation or 'operation'} ({duration:.2f}s)")
                if self.show_data and "outputs" in event.data:
                    self.output.write(f" | outputs: {event.data['outputs']}")
                self._write_metadata(event)
                self.output.write("\n")
            elif event.event_type == "error":
                error = event.data.get("error_message", "Unknown error")
                self.output.write(f"[{ts}] ERROR: {error}")
                self._write_metadata(event)
                self.output.write("\n")
            else:
                self.output.write(f"[{ts}] {event.event_type.upper()}: {event.operation}")
                if self.show_data:
                    # Show custom event data
                    data_items = []
                    for key, value in event.data.items():
                        if key not in ["user_id", "execution_id"]:  # Skip metadata we show separately
                            data_items.append(f"{key}={value}")
                    if data_items:
                        self.output.write(f" | {', '.join(data_items)}")
                self._write_metadata(event)
                self.output.write("\n")

            self._last_was_token = False

    def _write_metadata(self, event: Event) -> None:
        """Write metadata like user_id to output."""
        if not self.show_data:
            return

        metadata_items = []
        if user_id := event.data.get("user_id"):
            metadata_items.append(f"user={user_id}")

        if metadata_items:
            self.output.write(f" ({', '.join(metadata_items)})")
