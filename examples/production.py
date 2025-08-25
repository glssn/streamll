#!/usr/bin/env python
"""Production example - streaming to Redis.

Requires:
    - Redis running on localhost:6379
    - GEMINI_API_KEY or OPENROUTER_API_KEY in environment

Run with:
    uv run --env-file .env python examples/production.py
"""

import os

import dspy

import streamll
from streamll.sinks import RedisSink

# Configure Redis sink
redis_sink = RedisSink(url="redis://localhost:6379", stream_key="dspy_events")
streamll.configure(sinks=[redis_sink])


@streamll.instrument
class ProductionPipeline(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        return self.generate(question=question)


# Configure DSPy with LLM from environment
if os.getenv("GEMINI_API_KEY"):
    lm = dspy.LM("gemini/gemini-2.0-flash-exp")
elif os.getenv("OPENROUTER_API_KEY"):
    lm = dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct")
else:
    raise ValueError(
        "No LLM API key found. Set GEMINI_API_KEY or OPENROUTER_API_KEY.\n"
        "Run with: uv run --env-file .env python examples/production.py"
    )

# Configure DSPy with LLM only (no retrieval for this example)
dspy.configure(lm=lm)

# Run pipeline - events stream to Redis
pipeline = ProductionPipeline()
result = pipeline("How does photosynthesis work?")
