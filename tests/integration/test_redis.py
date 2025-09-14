import pytest
from nanoid import generate

from streamll.event_consumer import EventConsumer
from streamll.models import Event
from streamll.sinks.redis import RedisSink


def service_available(host: str = "localhost", port: int = 6379) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


requires_redis = pytest.mark.skipif(
    not service_available("localhost", 6379),
    reason="Redis not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)


class TestRedisIntegration:
    @requires_redis
    @pytest.mark.asyncio
    async def test_publish_and_consume(self):
        # Unique stream key for test isolation
        stream_key = f"test_stream_{generate(size=8)}"

        # Consumer setup
        consumer = EventConsumer(broker_url="redis://localhost:6379", target=stream_key)
        received_events = []

        @consumer.on("token")
        async def handle_token(event: Event):
            received_events.append(event)

        import asyncio

        consumer_task = asyncio.create_task(consumer.app.run())
        await asyncio.sleep(0.5)  # Let consumer start

        # Publish events
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        await sink.start()

        for i in range(3):
            event = Event(
                execution_id="test",
                event_type="token",
                data={"token": f"word_{i}", "index": i},
            )
            await sink.handle_event(event)

        await asyncio.sleep(1)  # Let events process
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

        # Verify
        assert len(received_events) == 3
        for i, event in enumerate(received_events):
            assert event.data["token"] == f"word_{i}"
            assert event.data["index"] == i
