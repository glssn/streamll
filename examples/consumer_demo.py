# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "streamll[redis]",
# ]
#
# [tool.uv.sources]
# streamll = { path = "../", editable = true }
# ///

import asyncio
import os
from streamll import RedisEventConsumer
from streamll.models import Event


async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    stream_key = "streamll:events"

    print(f"Listening for events on {redis_url}")
    print(f"Stream: {stream_key}")
    print("Press Ctrl+C to stop")

    consumer = RedisEventConsumer(broker_url=redis_url, target=stream_key)

    @consumer.on("start")
    async def handle_start(event: Event):
        print(f"START: {event.operation} (ID: {event.execution_id})")

    @consumer.on("token")
    async def handle_token(event: Event):
        token = event.data.get("token", "")
        print(token, end="", flush=True)

    @consumer.on("end")
    async def handle_end(event: Event):
        duration = event.data.get("duration", 0)
        print(f"\nEND: {event.operation} ({duration:.2f}s)\n")

    @consumer.on("error")
    async def handle_error(event: Event):
        error = event.data.get("error_message", "Unknown error")
        print(f"ERROR: {error}\n")

    try:
        await consumer.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
