#!/usr/bin/env python
# /// script
# dependencies = [
#   "dspy>=2.6.24",
#   "streamll @ file://..",
# ]
# ///
"""Basic StreamLL example showing trace() inside forward() method.

Requires environment variables:
    GEMINI_API_KEY or OPENROUTER_API_KEY for LLM access

Run with:
    uv run --env-file .env examples/basic.py
"""

import os
import time

import dspy

import streamll


class RetrievalQA(dspy.Module):
    """Example showing internal tracing for retrieval + generation."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        with streamll.trace("retrieving") as ctx:
            # Simulate document retrieval (long blocking operation)
            time.sleep(0.1)  # Simulate retrieval delay
            ctx.emit("documents_found", data={"count": 3, "query": question[:50]})

        with streamll.trace("generating") as ctx:
            # Generate answer based on retrieved context
            result = self.predict(question=question)
            ctx.emit(
                "tokens_generated",
                data={"answer_length": len(result.answer) if hasattr(result, "answer") else 0},
            )
            return result


# Configure DSPy with available LLM
if os.getenv("OPENROUTER_API_KEY"):
    dspy.configure(lm=dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct"))
elif os.getenv("GEMINI_API_KEY"):
    dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash-exp"))
else:
    raise ValueError(
        "No LLM API key found. Set OPENROUTER_API_KEY or GEMINI_API_KEY.\n"
        "Run with: uv run --env-file .env python examples/basic.py"
    )

# Run the example - events auto-stream to terminal
qa = RetrievalQA()
result = qa("What is the capital of France?")

