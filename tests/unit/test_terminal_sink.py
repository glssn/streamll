import io

from streamll.models import Event
from streamll.sinks.terminal import TerminalSink


class TestTerminalSink:
    def test_terminal_sink_creation(self):
        sink = TerminalSink()
        assert sink is not None
        assert not sink.is_running

    def test_terminal_sink_start_stop(self):
        sink = TerminalSink()

        sink.start()
        assert sink.is_running

        sink.stop()
        assert not sink.is_running

    def test_terminal_sink_handles_event(self):
        output = io.StringIO()
        sink = TerminalSink(output=output)
        sink.start()

        event = Event(
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
        sink = TerminalSink()
        sink.start()

        events = [
            Event(execution_id="test", event_type="start", operation="test_op"),
            Event(execution_id="test", event_type="end", operation="test_op"),
            Event(execution_id="test", event_type="token", data={"content": "Hello"}),
            Event(execution_id="test", event_type="error", data={"error_message": "Test error"}),
        ]

        for event in events:
            sink.handle_event(event)

        sink.stop()

    def test_terminal_sink_flush(self):
        sink = TerminalSink()
        sink.start()

        # Add event - no flush needed, outputs immediately
        event = Event(execution_id="test", event_type="custom")
        sink.handle_event(event)

        sink.stop()
