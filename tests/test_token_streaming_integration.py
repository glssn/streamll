#!/usr/bin/env python3
"""Integration tests for token streaming with real LLMs using uv inline metadata.

Run with: uv run tests/test_token_streaming_integration.py

# /// script
# dependencies = [
#   "dspy>=2.6.24",
#   "streamll",
#   "pytest",
# ]
# ///
"""

import os
import sys
from pathlib import Path

import pytest

# Add src to path so we can import streamll during development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamll
from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink


@pytest.fixture(autouse=True)
def reset_dspy():
    """Reset DSPy state between tests."""
    import dspy

    # Clear all global state
    dspy.configure()
    dspy.settings.configure()
    yield
    # Clean up after test
    dspy.configure()
    dspy.settings.configure()


class TokenCollectorSink(BaseSink):
    """Sink that specifically captures token events."""

    def __init__(self):
        super().__init__()
        self.token_events = []
        self.all_events = []
        self.is_running = False

    def handle_event(self, event: StreamllEvent) -> None:
        self.all_events.append(event)
        if event.event_type == "token":
            self.token_events.append(event)

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def flush(self) -> None:
        pass

    def _write_batch(self, batch):
        pass

    def get_tokens_for_field(self, field_name: str) -> list[str]:
        """Get tokens for a specific field."""
        return [
            event.data.get("token", "")
            for event in self.token_events
            if event.data.get("field") == field_name
        ]

    def get_reconstructed_text(self, field_name: str | None = None) -> str:
        """Reconstruct text from tokens."""
        if field_name:
            tokens = self.get_tokens_for_field(field_name)
        else:
            tokens = [e.data.get("token", "") for e in self.token_events]
        return "".join(tokens)


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"), reason="Requires OpenRouter API key")
def test_token_streaming_with_openrouter():
    """Test token-by-token streaming with OpenRouter models."""
    import dspy

    # Configure DSPy with OpenRouter - use DeepSeek which streams well
    lm = dspy.LM("openrouter/deepseek/deepseek-chat", max_tokens=50, cache=False)
    dspy.configure(lm=lm)

    # Set up token collector
    collector = TokenCollectorSink()
    collector.start()

    @streamll.instrument(sinks=[collector], stream_fields=["answer"])
    class TokenTestModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.predict = dspy.Predict("question -> answer")

        def forward(self, question):
            return self.predict(question=question)

    # Run with a question that should generate multiple tokens
    module = TokenTestModule()
    module("Tell me about cats")

    collector.stop()

    # Verify we got events
    assert len(collector.all_events) > 0, "Should capture events"
    assert len(collector.token_events) >= 1, (
        f"Should capture token events, got {len(collector.token_events)}"
    )

    # Check token events have correct structure
    for token_event in collector.token_events:
        assert token_event.event_type == "token"
        assert "token" in token_event.data
        assert "field" in token_event.data
        assert token_event.data["field"] == "answer"

    # Verify tokens reconstruct meaningful text
    answer_text = collector.get_reconstructed_text("answer")
    assert len(answer_text) > 0, "Should reconstruct some text from tokens"


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("OPENROUTER_API_KEY"), reason="Requires OpenRouter API key")
def test_multi_field_streaming():
    """Test streaming multiple fields (reasoning + answer)."""
    import dspy

    lm = dspy.LM("openrouter/deepseek/deepseek-chat", max_tokens=100, cache=False)
    dspy.configure(lm=lm)

    collector = TokenCollectorSink()
    collector.start()

    @streamll.instrument(sinks=[collector], stream_fields=["reasoning", "answer"])
    class CoTModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.cot = dspy.ChainOfThought("question -> answer")

        def forward(self, question):
            return self.cot(question=question)

    module = CoTModule()
    module("What are dogs?")

    collector.stop()

    # Should get tokens for both fields
    reasoning_tokens = collector.get_tokens_for_field("reasoning")
    answer_tokens = collector.get_tokens_for_field("answer")

    # At least one field should have tokens
    total_tokens = len(reasoning_tokens) + len(answer_tokens)
    assert total_tokens > 0, "Should get tokens for reasoning or answer fields"


if __name__ == "__main__":
    # Can run this file directly with: uv run tests/test_token_streaming_integration.py
    test_token_streaming_with_openrouter()
