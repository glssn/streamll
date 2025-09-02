from typing import Any

from streamll.brokers import create_broker
from streamll.models import StreamllEvent


class RabbitMQSink:
    def __init__(
        self,
        rabbitmq_url: str = "amqp://localhost:5672",
        queue: str = "streamll_events",
        exchange: str = "",
        **broker_kwargs: Any,
    ):
        self._broker = create_broker(rabbitmq_url, **broker_kwargs)
        self.queue = queue
        self.exchange = exchange
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    async def handle_event(self, event: StreamllEvent) -> None:
        """Publish event - let FastStream handle Pydantic serialization."""
        if not self.is_running:
            return

        async with self._broker:
            await self._broker.publish(event, queue=self.queue)
