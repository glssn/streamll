#!/usr/bin/env python
"""Basic StreamLL example - automatic terminal output.

Requires environment variables:
    GEMINI_API_KEY or OPENROUTER_API_KEY for LLM access

Run with:
    uv run --env-file .env python examples/basic.py
"""

import os

import dspy

import streamll


@streamll.instrument
class SimpleQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)


# Configure DSPy with available LLM from environment
if os.getenv("OPENROUTER_API_KEY"):
    # OpenRouter provides the best streaming support
    dspy.configure(lm=dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct"))
elif os.getenv("GEMINI_API_KEY"):
    dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash-exp"))
else:
    raise ValueError(
        "No LLM API key found. Set OPENROUTER_API_KEY or GEMINI_API_KEY.\n"
        "Run with: uv run --env-file .env python examples/basic.py"
    )

# Create and run module - events auto-stream to terminal
qa = SimpleQA()
result = qa("What is the capital of France?")


# Example 1: Basic usage - automatic start/end events
with streamll.trace("data_processing"):
    # Some work happens here
    result = qa("What is Python?")
    # That's it! You automatically get:
    # → [START] data_processing
    # → [END] data_processing (duration: 0.23s)

with streamll.trace("retrieval") as ctx:
    result = qa("What is machine learning?")
    ctx.emit("result_length", data={"length": len(result.answer)})
    # You get:
    # → [START] retrieval
    # → [CUSTOM] result_length {length: 125}
    # → [END] retrieval (duration: 0.45s)

try:
    with streamll.trace("risky_operation"):
        # If an error occurs, you get ERROR event instead of END
        result = qa("What is the meaning of life?")
        if "42" not in result.answer:
            raise ValueError("Wrong answer!")
except ValueError:
    pass
    # You got:
    # → [START] risky_operation
    # → [ERROR] risky_operation - ValueError: Wrong answer!

with streamll.trace("outer_operation") as outer, streamll.trace("inner_operation") as inner:
    result = qa("What is 2+2?")
    # Inner completes first

# Then outer completes
# Events show proper nesting:
# → [START] outer_operation
# → [START] inner_operation
# → [END] inner_operation
# → [END] outer_operation
