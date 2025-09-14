import os
import unittest

import dspy
import pytest

import streamll
from tests.test_helpers import EventCapturingSink


class TokenCapturingSink(EventCapturingSink):
    def __init__(self):
        super().__init__()
        self.token_events = []

    def handle_event(self, event):
        super().handle_event(event)
        if event.event_type == "token":
            self.token_events.append(event)


class TestRealLLMStreaming(unittest.TestCase):
    @pytest.mark.integration
    def test_openrouter_streaming(self):
        # Fail if API key missing
        if not os.getenv("OPENROUTER_API_KEY"):
            pytest.fail("OPENROUTER_API_KEY environment variable required for this test")
        # Configure LLM
        lm = dspy.LM(
            model="openrouter/deepseek/deepseek-chat",
            max_tokens=100,
            cache=False,
        )
        dspy.settings.configure(lm=lm)

        # Create sink and module
        sink = TokenCapturingSink()
        sink.start()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class SimpleQA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question):
                return self.predict(question=question)

        # Run module
        module = SimpleQA()
        module("Count from 1 to 5.")

        assert len(sink.events) > 0, "Should have captured events"
        assert any(e.event_type == "start" for e in sink.events), "Should have start event"
        assert any(e.event_type == "end" for e in sink.events), "Should have end event"

        assert len(sink.token_events) > 0, (
            f"No token events! Only got: {[e.event_type for e in sink.events]}"
        )
        assert len(sink.token_events) >= 1, (
            f"No token events ({len(sink.token_events)}), streaming not working"
        )

        first_token = sink.token_events[0]
        assert "field" in first_token.data, "Token event missing field"
        assert "token" in first_token.data, "Token event missing token content"
        assert "token_index" in first_token.data, "Token event missing index"

    @pytest.mark.integration
    def test_instrument_dspy_predict_directly(self):
        if not os.getenv("OPENROUTER_API_KEY"):
            pytest.fail("OPENROUTER_API_KEY environment variable required for this test")

        lm = dspy.LM(
            model="openrouter/deepseek/deepseek-chat",
            max_tokens=50,
            cache=False,
        )
        dspy.settings.configure(lm=lm)

        sink = TokenCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):

            @streamll.instrument
            class InstrumentedPredict(dspy.Predict):
                pass

            predict = InstrumentedPredict("question -> answer")
            result = predict(question="What is 2+2?")

        assert len(sink.events) > 0, "Should have captured events"
        assert result is not None, "Should have gotten a result"

        event_types = [e.event_type for e in sink.events]
        assert any("start" in t for t in event_types), f"No start event in {event_types}"
