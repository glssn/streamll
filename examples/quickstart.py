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


if not service_available("localhost", 1234):
    raise ValueError("Start local LLM on localhost:1234")

lm = dspy.LM(
    model="openai/deepseek-r1-distill-qwen-7b",
    api_key="test",
    api_base="http://localhost:1234/v1",
    max_tokens=200,
    cache=False,
)

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
    basic_qa = BasicQA()
    with streamll.configure():
        result = basic_qa("What is the capital of France?")
        print(f"Answer: {result.answer}")

    streaming_qa = StreamingQA()
    with streamll.configure():
        result = streaming_qa("Write a haiku about programming")
        print(f"Final answer: {result.answer}")
