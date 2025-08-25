#!/usr/bin/env python3
"""
StreamLL Quick Start Example
Run this to see token streaming in action!

Setup:
1. pip install streamll dspy
2. Set your environment variable: export OPENROUTER or GEMINI credentials
3. python quickstart.py
"""

import os
import sys
from datetime import UTC, datetime

import dspy

import streamll
from streamll import StreamllEvent, generate_event_id
from streamll.context import emit_event

# Configure DSPy - it automatically uses environment variables
if os.getenv("OPENROUTER_API_KEY"):
    # OpenRouter provides the best streaming support
    dspy.configure(lm=dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct"))
elif os.getenv("GEMINI_API_KEY"):
    dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash-exp"))
else:
    sys.exit(1)


# Example 1: Simple Q&A with token streaming


@streamll.instrument(stream_fields=["answer"])
class SimpleQA(dspy.Module):
    """Simple question-answering with streaming tokens."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")

    def forward(self, question):
        result = self.predict(question=question)
        return result


qa = SimpleQA()
result = qa("What is 2+2? Answer in one sentence.")

# Example 2: Chain of Thought with multi-field streaming


@streamll.instrument(stream_fields=["reasoning", "answer"])
class ReasoningQA(dspy.Module):
    """Chain of thought reasoning with streaming for both reasoning and answer."""

    def __init__(self):
        super().__init__()
        self.cot = dspy.ChainOfThought("question -> answer")

    def forward(self, question):
        return self.cot(question=question)


reasoner = ReasoningQA()
result = reasoner("If I have 3 apples and buy 2 more, then give 1 away, how many do I have?")

# Example 3: Custom events


@streamll.instrument
class CustomRAG(dspy.Module):
    """RAG pipeline with custom events for each stage."""

    def __init__(self):
        super().__init__()
        self.generate = dspy.Predict("context, question -> answer")

    def forward(self, question):
        # Emit custom retrieval event
        emit_event(
            StreamllEvent(
                event_id=generate_event_id(),
                execution_id="example-retrieval",
                timestamp=datetime.now(UTC),
                event_type="rag.retrieval",
                module_name=self.__class__.__name__,
                method_name="forward",
                data={"stage": "retrieving", "query": question, "source": "knowledge_base"},
            )
        )

        # Simulate retrieval
        context = "Machine learning is a subset of AI that enables systems to learn from data."

        # Emit custom generation event
        emit_event(
            StreamllEvent(
                event_id=generate_event_id(),
                execution_id="example-generation",
                timestamp=datetime.now(UTC),
                event_type="rag.generation",
                module_name=self.__class__.__name__,
                method_name="forward",
                data={"stage": "generating", "context_length": len(context)},
            )
        )

        # Generate answer
        result = self.generate(context=context, question=question)
        return result


rag = CustomRAG()
result = rag("What is machine learning?")
