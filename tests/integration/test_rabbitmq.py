import pytest
from nanoid import generate

from streamll.event_consumer import EventConsumer
from streamll.models import Event
from streamll.sinks.rabbitmq import RabbitMQSink


def service_available(host: str = "localhost", port: int = 5672) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


requires_rabbitmq = pytest.mark.skipif(
    not service_available("localhost", 5672),
    reason="RabbitMQ not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)


class TestRabbitMQIntegration:
    @requires_rabbitmq
    @pytest.mark.asyncio
    async def test_publish_and_consume(self):
        # Unique queue for test isolation
        queue = f"test_queue_{generate(size=8)}"

        # Consumer setup
        consumer = EventConsumer(broker_url="amqp://guest:guest@localhost:5672/", target=queue)
        received_event = None

        @consumer.on("error")
        async def handle_error(event: Event):
            nonlocal received_event
            received_event = event

        import asyncio

        consumer_task = asyncio.create_task(consumer.app.run())
        await asyncio.sleep(0.5)  # Let consumer start

        # Publish event
        sink = RabbitMQSink(rabbitmq_url="amqp://guest:guest@localhost:5672/", queue=queue)
        await sink.start()

        event = Event(
            execution_id="test",
            event_type="error",
            data={"error": "test_error", "code": 500},
        )
        await sink.handle_event(event)

        await asyncio.sleep(1)  # Let event process
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

        # Verify
        assert received_event is not None
        assert received_event.event_type == "error"
        assert received_event.data["error"] == "test_error"
        assert received_event.data["code"] == 500
