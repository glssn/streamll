import streamll
from streamll.sinks.terminal import TerminalSink


def test_import():
    assert streamll is not None
    assert hasattr(streamll, "trace")
    assert hasattr(streamll, "instrument")
    assert hasattr(streamll, "configure")


def test_trace_context_basic():
    with streamll.trace("test_operation"):
        pass


def test_trace_context_with_emit():
    with streamll.trace("custom_op") as ctx:
        ctx.emit("step1", data={"value": 1})
        ctx.emit("step2", data={"value": 2})


def test_configure_sinks():
    sink = TerminalSink()
    with streamll.configure(sinks=[sink]), streamll.trace("configured_op"):
        pass


def test_nested_traces():
    with streamll.trace("outer"), streamll.trace("inner"):
        pass
