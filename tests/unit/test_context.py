import time

import pytest

import streamll
from tests.test_helpers import EventCapturingSink


class TestTraceContext:
    def test_trace_basic_usage(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("test_op"):
            time.sleep(0.01)  # Simulate work

        sink.stop()

        # Should have start and end events
        assert len(sink.events) == 2
        assert sink.events[0].event_type == "start"
        assert sink.events[0].operation == "test_op"
        assert sink.events[1].event_type == "end"
        assert sink.events[1].operation == "test_op"

    def test_trace_with_custom_events(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("custom_op") as ctx:
            ctx.emit("step1", data={"value": 10})
            ctx.emit("step2", data={"value": 20})

        sink.stop()

        assert len(sink.events) == 4
        assert sink.events[0].event_type == "start"
        assert sink.events[1].event_type == "step1"
        assert sink.events[1].data["value"] == 10
        assert sink.events[2].event_type == "step2"
        assert sink.events[2].data["value"] == 20
        assert sink.events[3].event_type == "end"

    def test_trace_with_exception(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), pytest.raises(RuntimeError):
            with streamll.trace("error_op"):
                raise RuntimeError("Test error")

        sink.stop()

        assert len(sink.events) == 2
        assert sink.events[0].event_type == "start"
        assert sink.events[1].event_type == "error"
        assert "Test error" in sink.events[1].data["error_message"]

    def test_trace_nested_contexts(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("outer") as outer_ctx:
            outer_ctx.emit("outer_event")
            with streamll.trace("inner") as inner_ctx:
                inner_ctx.emit("inner_event")

        sink.stop()

        # outer start, outer event, inner start, inner event, inner end, outer end
        assert len(sink.events) == 6
        event_types = [e.event_type for e in sink.events]
        assert event_types == ["start", "outer_event", "start", "inner_event", "end", "end"]

    def test_trace_execution_id(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("op1") as ctx:
            ctx.emit("event1")
            ctx.emit("event2")

        sink.stop()

        # All events should share same execution_id
        exec_id = sink.events[0].execution_id
        assert all(e.execution_id == exec_id for e in sink.events)

    def test_trace_operation_name(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("my_operation"):
            pass

        sink.stop()

        assert all(e.operation == "my_operation" for e in sink.events)

    def test_trace_timing_metadata(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]), streamll.trace("timed_op"):
            time.sleep(0.05)

        sink.stop()

        start_event = sink.events[0]
        end_event = sink.events[1]

        assert start_event.timestamp <= end_event.timestamp
        # Duration should be at least 50ms
        duration = (end_event.timestamp - start_event.timestamp).total_seconds()
        assert duration >= 0.04  # Allow some tolerance

    def test_trace_without_configuration(self):
        # Should not raise error
        with streamll.trace("no_sink_op") as ctx:
            ctx.emit("test")
            pass

    def test_trace_data_passthrough(self):
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):
            with streamll.trace("data_op", user="test") as ctx:
                ctx.emit("event", data={"count": 5})

        sink.stop()

        # Check metadata is captured in data field
        assert sink.events[0].data.get("user") == "test"
        # Check custom event data
        custom_event = [e for e in sink.events if e.event_type == "event"][0]
        assert custom_event.data["count"] == 5
