"""Integration tests for real LLM token streaming."""

import os
import unittest

import dspy
import pytest

import streamll
from streamll.sinks.base import BaseSink


class TokenCapturingSink(BaseSink):
    """Sink that captures token events for testing."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.token_events = []
        self.is_running = False

    def handle_event(self, event):
        """Capture events, especially token events."""
        self.events.append(event)
        if event.event_type == "token":
            self.token_events.append(event)

    def start(self):
        """Start the sink."""
        self.is_running = True

    def stop(self):
        """Stop the sink."""
        self.is_running = False

    def flush(self):
        """Flush any buffered events."""
        pass

    def _write_batch(self, batch):
        """Write batch (not used in test sink)."""
        pass


class TestRealLLMStreaming(unittest.TestCase):
    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"), reason="No OpenRouter API key")
    def test_openrouter_streaming(self):
        """Test streaming with OpenRouter."""
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

        # Verify we got events
        assert len(sink.events) > 0, "Should have captured events"
        assert any(e.event_type == "start" for e in sink.events), "Should have start event"
        assert any(e.event_type == "end" for e in sink.events), "Should have end event"
        
        # CRITICAL: Verify we actually got token streaming events
        assert len(sink.token_events) > 0, f"No token events! Only got: {[e.event_type for e in sink.events]}"
        assert len(sink.token_events) >= 3, f"Too few tokens ({len(sink.token_events)}), streaming might be broken"
        
        # Verify tokens have expected structure
        first_token = sink.token_events[0]
        assert "field" in first_token.data, "Token event missing field"
        assert "token" in first_token.data, "Token event missing token content"
        assert "token_index" in first_token.data, "Token event missing index"
