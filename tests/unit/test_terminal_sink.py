"""Unit tests for TerminalSink."""

import io

from streamll.models import StreamllEvent
from streamll.sinks.terminal import TerminalSink


class TestTerminalSink:
    """Test the TerminalSink."""

    def test_terminal_sink_creation(self):
        """Test creating a terminal sink."""
        sink = TerminalSink()
        assert sink is not None
        assert not sink.is_running

    def test_terminal_sink_start_stop(self):
        """Test starting and stopping terminal sink."""
        sink = TerminalSink()

        sink.start()
        assert sink.is_running

        sink.stop()
        assert not sink.is_running

    def test_terminal_sink_handles_event(self):
        """Test terminal sink handles events."""
        output = io.StringIO()
        sink = TerminalSink(output=output)
        sink.start()

        event = StreamllEvent(
            execution_id="test_exec",
            event_type="custom",
            operation="test_op",
            data={"message": "hello"},
        )

        sink.handle_event(event)

        result = output.getvalue()

        assert len(result) > 0
        assert "CUSTOM" in result
        assert "test_op" in result

        sink.stop()

    def test_terminal_sink_formats_events(self):
        """Test terminal sink formats different event types."""
        sink = TerminalSink()
        sink.start()

        events = [
            StreamllEvent(execution_id="test", event_type="start", operation="test_op"),
            StreamllEvent(execution_id="test", event_type="end", operation="test_op"),
            StreamllEvent(execution_id="test", event_type="token", data={"content": "Hello"}),
            StreamllEvent(
                execution_id="test", event_type="error", data={"error_message": "Test error"}
            ),
        ]

        for event in events:
            sink.handle_event(event)

        sink.stop()

    def test_terminal_sink_flush(self):
        """Test terminal sink flush does nothing (no buffering)."""
        sink = TerminalSink()
        sink.start()

        # Add event - no flush needed, outputs immediately
        event = StreamllEvent(execution_id="test", event_type="custom")
        sink.handle_event(event)

        sink.stop()
