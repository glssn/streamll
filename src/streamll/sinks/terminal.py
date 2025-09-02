import sys

from streamll.models import StreamllEvent


class TerminalSink:
    def __init__(self, show_tokens: bool = True, output=None):
        self.show_tokens = show_tokens
        self.output = output or sys.stdout
        self.is_running = False
        self._last_was_token = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def handle_event(self, event: StreamllEvent) -> None:
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
                self.output.write(f"[{ts}] START {event.operation or 'operation'}\n")
            elif event.event_type == "end":
                duration = event.data.get("duration", 0)
                self.output.write(
                    f"[{ts}] END {event.operation or 'operation'} ({duration:.2f}s)\n"
                )
            elif event.event_type == "error":
                error = event.data.get("error_message", "Unknown error")
                self.output.write(f"[{ts}] ERROR: {error}\n")
            else:
                self.output.write(f"[{ts}] {event.event_type.upper()}: {event.operation}\n")

            self._last_was_token = False
