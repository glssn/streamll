# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "streamll[redis]",
#     "dspy>=2.7.0",
# ]
#
# [tool.uv.sources]
# streamll = { path = "../", editable = true }
# ///

import os
import socket
import dspy
import streamll
from streamll.sinks import RedisSink  # type: ignore[possibly-unbound-import]


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
    max_tokens=400,
    cache=False,
)

dspy.settings.configure(lm=lm)


@streamll.instrument(stream_fields=["response"])
class AssistantModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("query -> response")

    def forward(self, query):
        return self.predict(query=query)


if __name__ == "__main__":
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    stream_key = "streamll:events"
    redis_sink = RedisSink(redis_url=redis_url, stream_key=stream_key)
    assistant = AssistantModule()

    with streamll.configure(sinks=[redis_sink]):
        queries = ["Briefly explain quantum computing", "What's the future of AI, as a haiku?"]

        for query in queries:
            result = assistant(query=query)

    print(f"View events with: redis-cli XREAD COUNT 10 STREAMS {stream_key} 0")
