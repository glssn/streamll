# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "streamll",
#     "dspy>=2.7.0",
# ]
#
# [tool.uv.sources]
# streamll = { path = "../", editable = true }
# ///

import socket
import random
import dspy
import streamll


def service_available(host: str = "localhost", port: int = 1234) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


if service_available("localhost", 1234):
    lm = dspy.LM(
        model="openai/deepseek-r1-distill-qwen-7b",
        api_key="test",
        api_base="http://localhost:1234/v1",
        cache=False,
    )
else:
    raise ValueError("Start local LLM on localhost:1234")
dspy.settings.configure(lm=lm)


@streamll.instrument
class RAGPipeline(dspy.Module):
    def __init__(self):
        self.docs = [
            "AI is a field of computer science",
            "Machine learning uses algorithms to learn patterns",
            "Neural networks are inspired by the brain",
            "Deep learning uses multiple layers",
            "Data science involves extracting insights from data",
        ]
        self.generate = dspy.Predict("question, docs -> answer")

    def forward(self, question, user_id=None):
        with streamll.trace("retrieval", user_id=user_id) as ctx:
            num_docs = random.randint(1, 3)
            retrieved_docs = random.sample(self.docs, num_docs)
            ctx.emit("docs_found", data={"count": num_docs})

        return self.generate(question=question, docs=" ".join(retrieved_docs))


rag = RAGPipeline()
result = rag("What is machine learning?", user_id="user123")
