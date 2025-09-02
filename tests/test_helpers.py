"""Common test helpers and fixtures."""

from streamll.models import StreamllEvent


class EventCapturingSink:
    """Test sink that captures events for verification."""

    def __init__(self):
        self.events = []
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def handle_event(self, event: StreamllEvent) -> None:
        """Capture events immediately."""
        self.events.append(event)

    def clear(self) -> None:
        """Clear captured events."""
        self.events.clear()
