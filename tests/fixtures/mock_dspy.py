"""Mock DSPy components for testing without API keys."""

from unittest.mock import MagicMock

import dspy


class MockLM:
    """Mock language model that simulates token streaming."""

    def __init__(self, model="mock-model"):
        self.model = model
        self.history = []

    def __call__(self, prompt, stream=False, **kwargs):
        """Generate mock response."""
        response = "This is a mock response for testing purposes."

        if stream:
            # Simulate token streaming
            tokens = response.split()
            for i, token in enumerate(tokens):
                yield {
                    "choices": [
                        {
                            "delta": {"content": token + (" " if i < len(tokens) - 1 else "")},
                            "index": 0,
                        }
                    ]
                }
        else:
            return {"choices": [{"message": {"content": response}}]}

    def inspect_history(self, n=1):
        """Return mock history."""
        return self.history[-n:] if n else self.history


class MockChainOfThought(dspy.Module):
    """Mock ChainOfThought module for testing."""

    def __init__(self, signature):
        super().__init__()
        self.signature = signature
        self.predict = MagicMock()
        self.predict.return_value = dspy.Prediction(
            answer="Mock answer", reasoning="Mock reasoning"
        )

    def forward(self, **kwargs):
        """Mock forward pass."""
        return self.predict(**kwargs)


class MockSignature:
    """Mock DSPy signature."""

    def __init__(self, input_fields, output_fields):
        self.input_fields = input_fields
        self.output_fields = output_fields


def setup_mock_dspy():
    """Configure DSPy with mock LM for testing."""
    mock_lm = MockLM()
    dspy.settings.configure(lm=mock_lm)
    return mock_lm


def create_mock_module():
    """Create a mock DSPy module for testing instrumentation."""

    class TestModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.cot = MockChainOfThought("question -> answer")

        def forward(self, question):
            return self.cot(question=question)

    return TestModule
