import dspy

import streamll
from tests.test_helpers import EventCapturingSink


def test_set_context_propagates_to_events():
    sink = EventCapturingSink()

    @streamll.instrument(sinks=[sink])
    class TestModule(dspy.Module):
        def __init__(self):
            super().__init__()

        def forward(self, query):
            # Simple forward that doesn't require LLM
            return {"output": f"Processed: {query}"}

    # Set conversation context
    streamll.set_context(conversation_id="conv_123", user_id="user_456")

    # Create and run module
    module = TestModule()
    module(query="test query")

    # Check that events contain the conversation context
    assert len(sink.events) > 0

    for event in sink.events:
        assert "conversation_id" in event.data
        assert event.data["conversation_id"] == "conv_123"
        assert "user_id" in event.data
        assert event.data["user_id"] == "user_456"


def test_context_isolation_between_calls():
    sink = EventCapturingSink()

    @streamll.instrument(sinks=[sink])
    class TestModule(dspy.Module):
        def __init__(self):
            super().__init__()

        def forward(self, query):
            return {"output": f"Processed: {query}"}

    module = TestModule()

    # First call with context A
    streamll.set_context(conversation_id="conv_A")
    module(query="query A")
    events_a = sink.events.copy()
    sink.events.clear()

    # Second call with context B
    streamll.set_context(conversation_id="conv_B")
    module(query="query B")
    events_b = sink.events.copy()

    # Verify context isolation
    for event in events_a:
        assert event.data.get("conversation_id") == "conv_A"

    for event in events_b:
        assert event.data.get("conversation_id") == "conv_B"


def test_context_with_trace():
    sink = EventCapturingSink()

    with streamll.configure(sinks=[sink]):
        # Set conversation context
        streamll.set_context(conversation_id="conv_trace", session_id="sess_123")

        # Use trace context
        with streamll.trace("test_operation") as ctx:
            ctx.emit("custom_event", data={"key": "value"})

    # Check events
    assert len(sink.events) >= 2  # start, custom, end

    for event in sink.events:
        # The trace context itself doesn't get conversation context
        # but emit within trace should
        if event.event_type == "custom_event":
            assert "conversation_id" in event.data
            assert event.data["conversation_id"] == "conv_trace"
            assert "session_id" in event.data
            assert event.data["session_id"] == "sess_123"


def test_empty_context():
    sink = EventCapturingSink()

    @streamll.instrument(sinks=[sink])
    class TestModule(dspy.Module):
        def __init__(self):
            super().__init__()

        def forward(self, query):
            return {"output": f"Processed: {query}"}

    # Clear any existing context and don't set any new context
    streamll.set_context()

    module = TestModule()
    module(query="test query")

    # Events should still work, just without extra context
    assert len(sink.events) > 0

    # Events should have basic data but no conversation_id
    for event in sink.events:
        assert event.execution_id is not None
        assert event.event_type is not None


def test_context_overwrite():
    sink = EventCapturingSink()

    @streamll.instrument(sinks=[sink])
    class TestModule(dspy.Module):
        def __init__(self):
            super().__init__()

        def forward(self, query):
            return {"output": f"Processed: {query}"}

    module = TestModule()

    # Set initial context
    streamll.set_context(conversation_id="old_id", user_id="old_user")

    # Overwrite with new context
    streamll.set_context(conversation_id="new_id", user_id="new_user")

    module(query="test query")

    # Should have new context values
    for event in sink.events:
        assert event.data.get("conversation_id") == "new_id"
        assert event.data.get("user_id") == "new_user"
        # Old values should not be present
        assert event.data.get("conversation_id") != "old_id"
