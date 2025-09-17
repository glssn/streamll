import pytest
import dspy

from streamll.streaming import wrap_with_streaming


class MockSink:
    def __init__(self):
        self.events = []
        self.tokens = []

    def handle_event(self, event):
        self.events.append(event)
        if event.event_type == "token":
            self.tokens.append(event.data.get("token", ""))

    def start(self):
        pass

    def stop(self):
        pass

    @property
    def is_running(self):
        return True


class TestStreaming:
    def test_wrap_with_streaming_no_predictors(self):
        """Test that wrap_with_streaming returns original method when no predictors found."""

        class EmptyModule:
            pass

        module = EmptyModule()

        def original_forward():
            return "original"

        wrapped = wrap_with_streaming(original_forward, module, ["answer"])
        result = wrapped()

        assert result == "original"

    def test_token_reconstruction_matches_final_answer(self):
        """Test that collected tokens can reconstruct the final answer."""

        # Skip if no local model available
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(("localhost", 1234)) != 0:
                pytest.skip("Local model not available")
            sock.close()
        except OSError:
            pytest.skip("Local model not available")

        # Configure with local model
        lm = dspy.LM(
            model="openai/deepseek-r1-distill-qwen-7b",
            api_key="test",
            api_base="http://localhost:1234/v1",
            max_tokens=20,
            cache=False,
        )
        dspy.settings.configure(lm=lm)

        import streamll

        sink = MockSink()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class SimpleQA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question):
                return self.predict(question=question)

        module = SimpleQA()
        module(question="What is 2+2?")

        # Verify we got tokens
        assert len(sink.tokens) > 0, "Should capture token events"

        # Verify tokens are strings
        for token in sink.tokens:
            assert isinstance(token, str), f"Token should be string, got {type(token)}"

        # Verify event structure
        token_events = [e for e in sink.events if e.event_type == "token"]
        assert len(token_events) > 0, "Should have token events"

        for event in token_events:
            assert "field" in event.data
            assert "token" in event.data
            assert "token_index" in event.data
            assert event.data["field"] == "answer"

    def test_multiple_stream_fields(self):
        """Test streaming with multiple fields specified."""

        # Skip if no local model available
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(("localhost", 1234)) != 0:
                pytest.skip("Local model not available")
            sock.close()
        except OSError:
            pytest.skip("Local model not available")

        lm = dspy.LM(
            model="openai/deepseek-r1-distill-qwen-7b",
            api_key="test",
            api_base="http://localhost:1234/v1",
            max_tokens=30,
            cache=False,
        )
        dspy.settings.configure(lm=lm)

        import streamll

        sink = MockSink()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class QA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question):
                return self.predict(question=question)

        module = QA()
        module(question="Count to 3")

        # Should get tokens for the answer field
        assert len(sink.tokens) > 0, "Should capture tokens"

        # All events should be for the 'answer' field
        token_events = [e for e in sink.events if e.event_type == "token"]
        for event in token_events:
            assert event.data["field"] == "answer"

    def test_no_streaming_without_stream_fields(self):
        """Test that no token events are emitted when stream_fields is empty."""

        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(("localhost", 1234)) != 0:
                pytest.skip("Local model not available")
            sock.close()
        except OSError:
            pytest.skip("Local model not available")

        lm = dspy.LM(
            model="openai/deepseek-r1-distill-qwen-7b",
            api_key="test",
            api_base="http://localhost:1234/v1",
            max_tokens=20,
            cache=False,
        )
        dspy.settings.configure(lm=lm)

        import streamll

        sink = MockSink()

        @streamll.instrument(sinks=[sink])  # No stream_fields
        class QA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question):
                return self.predict(question=question)

        module = QA()
        module(question="What is 2+2?")

        # Should get start/end events but no token events
        event_types = {e.event_type for e in sink.events}
        assert "start" in event_types
        assert "end" in event_types
        assert "token" not in event_types
        assert len(sink.tokens) == 0
