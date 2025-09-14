from typing import Any

from faststream.rabbit import RabbitBroker

from streamll.models import Event


class RabbitMQSink:
    def __init__(
        self,
        rabbitmq_url: str = "amqp://localhost:5672",
        queue: str = "streamll_events",
        exchange: str = "",
        **broker_kwargs: Any,
    ):
        self.broker = RabbitBroker(rabbitmq_url, **broker_kwargs)
        self.queue = queue
        self.exchange = exchange
        self.is_running = False
        self._connected = False

    async def start(self) -> None:
        if not self._connected:
            await self.broker.connect()
            self._connected = True
        self.is_running = True

    async def stop(self) -> None:
        self.is_running = False
        if self._connected:
            await self.broker.stop()
            self._connected = False

    async def handle_event(self, event: Event) -> None:
        if not self.is_running:
            return

        if not self._connected:
            await self.start()

        await self.broker.publish(event, queue=self.queue)
