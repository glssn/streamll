#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "streamll",
#     "dspy>=2.7.0",
# ]
# ///

import os
import dspy
import streamll

# Configure LLM
if os.getenv("OPENROUTER_API_KEY"):
    lm = dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct", cache=False)
elif os.getenv("GEMINI_API_KEY"):
    lm = dspy.LM("gemini/gemini-2.0-flash-exp", cache=False)
else:
    raise ValueError("Set OPENROUTER_API_KEY or GEMINI_API_KEY")

dspy.settings.configure(lm=lm)


# Example 1: Basic instrumentation (no streaming)
@streamll.instrument
class BasicQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)


# Example 2: With token streaming
@streamll.instrument(stream_fields=["answer"])
class StreamingQA(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        return self.predict(question=question)


if __name__ == "__main__":
    print("🚀 streamll Quickstart\n")

    # Example 1: Basic usage
    print("1. Basic instrumentation:")
    basic_qa = BasicQA()
    with streamll.configure():  # Uses TerminalSink by default
        result = basic_qa("What is the capital of France?")
        print(f"Answer: {result.answer}\n")

    # Example 2: Token streaming
    print("2. Token streaming:")
    streaming_qa = StreamingQA()
    with streamll.configure():
        result = streaming_qa("Write a haiku about programming")
        print(f"\nFinal answer: {result.answer}")
