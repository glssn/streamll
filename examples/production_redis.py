#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "streamll[redis]",
#     "dspy>=2.7.0",
# ]
# ///

import os
import dspy
import streamll
from streamll.sinks import RedisSink  # type: ignore[possibly-unbound-import]

# Configure LLM
if os.getenv("OPENROUTER_API_KEY"):
    lm = dspy.LM("openrouter/qwen/qwen-2.5-72b-instruct", cache=False)
elif os.getenv("GEMINI_API_KEY"):
    lm = dspy.LM("gemini/gemini-2.0-flash-exp", cache=False)
else:
    raise ValueError("Set OPENROUTER_API_KEY or GEMINI_API_KEY")

dspy.settings.configure(lm=lm)


@streamll.instrument(stream_fields=["response"])
class AssistantModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("query -> response")

    def forward(self, query):
        return self.predict(query=query)


if __name__ == "__main__":
    # Redis configuration
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    stream_key = "streamll:events"

    print(f"🔄 Streaming to Redis: {redis_url}")
    print(f"📝 Stream key: {stream_key}\n")

    # Configure Redis sink
    redis_sink = RedisSink(redis_url=redis_url, stream_key=stream_key)

    assistant = AssistantModule()

    with streamll.configure(sinks=[redis_sink]):
        # Process multiple queries
        queries = [
            "Explain quantum computing",
            "What's the future of AI?",
            "How do neural networks work?",
        ]

        for i, query in enumerate(queries, 1):
            print(f"Query {i}: {query}")
            result = assistant(query=query)
            print("✅ Streamed to Redis\n")

    print("🏁 All events sent to Redis!")
    print(f"💡 View events with: redis-cli XREAD COUNT 10 STREAMS {stream_key} 0")
