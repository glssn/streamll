#!/usr/bin/env python3
"""StreamLL Quick Start - Token streaming example."""

import os

import dspy

import streamll

# Configure LLM
if os.getenv("OPENROUTER_API_KEY"):
    dspy.configure(lm=dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct"))
elif os.getenv("GEMINI_API_KEY"):
    dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash-exp"))
else:
    raise ValueError("Set OPENROUTER_API_KEY or GEMINI_API_KEY")


@streamll.instrument(stream_fields=["answer"])
class StreamingQA(dspy.Module):
    """Q&A with real-time token streaming."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)


@streamll.instrument(stream_fields=["reasoning", "answer"])
class ReasoningQA(dspy.Module):
    """Chain of thought with streaming for both fields."""

    def __init__(self):
        super().__init__()
        self.cot = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        return self.cot(question=question)


# Example 1: Simple streaming
qa = StreamingQA()
qa("What is 2+2? Answer in one sentence.")

# Example 2: Multi-field streaming
reasoner = ReasoningQA()
reasoner("If I have 3 apples and buy 2 more, then give 1 away, how many do I have?")
