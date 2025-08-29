#!/usr/bin/env python3
"""StreamLL Basic Example - Minimal working demo."""

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


@streamll.instrument
class SimpleQA(dspy.Module):
    """Simple Q&A module with automatic event tracking."""
    
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
    
    def forward(self, question):
        return self.predict(question=question)


# Use the module - events are automatically emitted to terminal
qa = SimpleQA()
result = qa("What is 2+2?")
print(f"\nAnswer: {result.answer}")