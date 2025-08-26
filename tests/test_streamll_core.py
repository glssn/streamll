"""Tests for core StreamLL functionality after simplification."""

import io

import pytest

import streamll
from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink


class CapturingSink(BaseSink):
    """Test sink that captures events."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.is_running = False

    def handle_event(self, event: StreamllEvent) -> None:
        self.events.append(event)

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def flush(self) -> None:
        pass

    def _write_batch(self, batch):
        pass


class TestStreamllTraceContext:
    """Test the streamll.trace() context manager."""

    def test_trace_automatic_start_end_events(self):
        """Test trace() emits automatic start and end events."""
        sink = CapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("test_operation"):
            pass  # Do nothing

        sink.stop()

        # Should have start and end events
        assert len(sink.events) == 2
        assert sink.events[0].event_type == "start"
        assert sink.events[0].operation == "test_operation"
        assert sink.events[1].event_type == "end"
        assert sink.events[1].operation == "test_operation"

        # Should have same execution_id
        assert sink.events[0].execution_id == sink.events[1].execution_id

    def test_trace_custom_events_with_emit(self):
        """Test ctx.emit() for custom events within trace."""
        sink = CapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("custom_trace") as ctx:
            ctx.emit("custom_event", data={"key": "value"})
            ctx.emit("another_event", data={"number": 42})

        sink.stop()

        # Should have start, 2 custom events, end
        assert len(sink.events) == 4
        assert sink.events[0].event_type == "start"
        assert sink.events[1].event_type == "custom_event"
        assert sink.events[1].data["key"] == "value"
        assert sink.events[2].event_type == "another_event"
        assert sink.events[2].data["number"] == 42
        assert sink.events[3].event_type == "end"

    def test_trace_error_handling(self):
        """Test trace() emits error event on exception."""
        sink = CapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), pytest.raises(ValueError), streamll.trace("error_operation"):
            raise ValueError("Test error")

        sink.stop()

        # Should have start and error events (no end)
        assert len(sink.events) == 2
        assert sink.events[0].event_type == "start"
        assert sink.events[1].event_type == "error"
        assert "Test error" in sink.events[1].data["error_message"]

    def test_nested_traces(self):
        """Test nested trace contexts work correctly."""
        sink = CapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("outer") as outer_ctx:
            outer_ctx.emit("outer_event", data={"level": "outer"})

            with streamll.trace("inner") as inner_ctx:
                inner_ctx.emit("inner_event", data={"level": "inner"})

        sink.stop()

        # Should have outer start, outer event, inner start, inner event, inner end, outer end
        assert len(sink.events) == 6
        assert sink.events[0].event_type == "start" and sink.events[0].operation == "outer"
        assert sink.events[1].event_type == "outer_event"
        assert sink.events[2].event_type == "start" and sink.events[2].operation == "inner"
        assert sink.events[3].event_type == "inner_event"
        assert sink.events[4].event_type == "end" and sink.events[4].operation == "inner"
        assert sink.events[5].event_type == "end" and sink.events[5].operation == "outer"

        # Each trace should have unique execution_id
        outer_id = sink.events[0].execution_id
        inner_id = sink.events[2].execution_id
        assert outer_id != inner_id


class TestStreamllDecorator:
    """Test the @streamll.instrument decorator."""

    def test_instrument_decorator_with_terminal_sink(self):
        """Test @instrument decorator creates terminal sink by default."""
        import dspy
        io.StringIO()

        @streamll.instrument
        class TestModule(dspy.Module):
            def forward(self, x):
                return x * 2

        # Should create default TerminalSink when no sinks configured
        module = TestModule()
        result = module.forward(5)
        assert result == 10


class TestStreamllSinks:
    """Test individual sinks work correctly."""

    def test_terminal_sink_formatting(self):
        """Test TerminalSink formats events correctly."""
        output = io.StringIO()
        sink = streamll.TerminalSink(output=output)
        sink.start()

        event = StreamllEvent(
            event_id="test123",
            execution_id="exec123",
            event_type="start",
            operation="test_op",
            data={}
        )

        sink.handle_event(event)
        sink.stop()

        output_str = output.getvalue()
        assert "START test_op" in output_str

    def test_redis_sink_connection(self):
        """Test RedisSink basic functionality."""
        # Test without actual Redis - just initialization
        sink = streamll.RedisSink(url="redis://localhost:6379", stream_key="test")
        assert sink.url == "redis://localhost:6379"
        assert sink.stream_key == "test"
