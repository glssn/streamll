#!/usr/bin/env python
# /// script
# dependencies = [
#   "dspy>=2.6.24",
#   "streamll @ file://..",
# ]
# ///
"""Example showing streamll.trace() inside DSPy module forward methods.

This pattern lets you track internal operations within your DSPy modules,
giving you detailed visibility into complex processing pipelines.

Requires environment variables:
    GEMINI_API_KEY or OPENROUTER_API_KEY for LLM access

Run with:
    uv run --env-file .env examples/trace_inside_forward.py
"""

import os

import dspy

import streamll


class DetailedQA(dspy.Module):
    """Example showing trace() inside forward method for detailed tracking."""

    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("question -> answer")
        self.refine = dspy.Predict("question, first_answer -> refined_answer")

    def forward(self, question):
        with streamll.trace("question_analysis") as ctx:
            # Analyze the question complexity
            word_count = len(question.split())
            complexity = "complex" if word_count > 10 else "simple"
            ctx.emit("analysis_complete", data={"word_count": word_count, "complexity": complexity})

        with streamll.trace("initial_prediction"):
            # Get first answer
            initial = self.predict(question=question)

        with streamll.trace("answer_refinement") as ctx:
            # Refine the answer based on complexity
            if complexity == "complex":
                ctx.emit("refinement_needed", data={"reason": "complex_question"})
                refined = self.refine(question=question, first_answer=initial.answer)
                return refined
            else:
                ctx.emit("refinement_skipped", data={"reason": "simple_question"})
                return initial


class MultiStepRAG(dspy.Module):
    """Example showing detailed RAG pipeline with internal tracing."""

    def __init__(self):
        super().__init__()
        self.retrieve = dspy.Predict("query -> retrieved_docs")
        self.synthesize = dspy.Predict("query, docs -> answer")

    def forward(self, query):
        with streamll.trace("query_preprocessing") as ctx:
            # Clean and prepare query
            cleaned_query = query.strip().lower()
            ctx.emit(
                "query_cleaned",
                data={"original_length": len(query), "cleaned_length": len(cleaned_query)},
            )

        with streamll.trace("document_retrieval") as ctx:
            # Retrieve relevant documents
            docs = self.retrieve(query=cleaned_query)
            doc_count = (
                len(docs.retrieved_docs.split("\n")) if hasattr(docs, "retrieved_docs") else 3
            )
            ctx.emit(
                "retrieval_complete",
                data={"documents_found": doc_count, "query_processed": cleaned_query},
            )

        with streamll.trace("answer_synthesis") as ctx:
            # Synthesize final answer
            ctx.emit("synthesis_starting", data={"doc_count": doc_count})
            result = self.synthesize(
                query=cleaned_query,
                docs=docs.retrieved_docs if hasattr(docs, "retrieved_docs") else "Mock docs",
            )
            ctx.emit(
                "synthesis_complete",
                data={"answer_length": len(result.answer) if hasattr(result, "answer") else 0},
            )
            return result


# Configure DSPy with available LLM
if os.getenv("OPENROUTER_API_KEY"):
    dspy.configure(lm=dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct"))
elif os.getenv("GEMINI_API_KEY"):
    dspy.configure(lm=dspy.LM("gemini/gemini-2.0-flash-exp"))
else:
    pass
    # For demo purposes, let's still show the structure


def main():
    qa = DetailedQA()

    # This will show detailed tracing inside the forward method:
    # [START] question_analysis
    # [CUSTOM] analysis_complete {word_count: 8, complexity: "simple"}
    # [END] question_analysis
    # [START] initial_prediction
    # [END] initial_prediction
    # [START] answer_refinement
    # [CUSTOM] refinement_skipped {reason: "simple_question"}
    # [END] answer_refinement

    qa("What is the capital of France?")

    # This will trigger refinement:
    qa(
        "Can you explain the historical significance of the French Revolution and its impact on modern democratic institutions worldwide?"
    )

    rag = MultiStepRAG()

    # This will show the full RAG pipeline:
    # [START] query_preprocessing
    # [CUSTOM] query_cleaned {original_length: 35, cleaned_length: 33}
    # [END] query_preprocessing
    # [START] document_retrieval
    # [CUSTOM] retrieval_complete {documents_found: 3, query_processed: "..."}
    # [END] document_retrieval
    # [START] answer_synthesis
    # [CUSTOM] synthesis_starting {doc_count: 3}
    # [CUSTOM] synthesis_complete {answer_length: 150}
    # [END] answer_synthesis

    rag("How does photosynthesis work?")


if __name__ == "__main__":
    main()
