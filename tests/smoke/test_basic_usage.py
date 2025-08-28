"""Smoke tests for basic StreamLL usage."""

import streamll
from streamll.sinks.terminal import TerminalSink


def test_import():
    """Test that streamll can be imported."""
    assert streamll is not None
    assert hasattr(streamll, "trace")
    assert hasattr(streamll, "instrument")
    assert hasattr(streamll, "configure")


def test_trace_context_basic():
    """Test basic trace context usage."""
    # Should not raise any errors
    with streamll.trace("test_operation"):
        pass


def test_trace_context_with_emit():
    """Test trace context with custom events."""
    with streamll.trace("custom_op") as ctx:
        ctx.emit("step1", data={"value": 1})
        ctx.emit("step2", data={"value": 2})


def test_configure_sinks():
    """Test configuring sinks."""
    sink = TerminalSink()
    with streamll.configure(sinks=[sink]), streamll.trace("configured_op"):
        pass


def test_nested_traces():
    """Test nested trace contexts."""
    with streamll.trace("outer"), streamll.trace("inner"):
        pass
