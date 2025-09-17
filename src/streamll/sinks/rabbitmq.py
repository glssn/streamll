import json
from typing import Any

import pika

from streamll.models import Event


class RabbitMQSink:
    def __init__(
        self,
        rabbitmq_url: str = "amqp://localhost:5672",
        queue: str = "streamll_events",
        exchange: str = "",
        **connection_kwargs: Any,
    ):
        self.rabbitmq_url = rabbitmq_url
        self.queue = queue
        self.exchange = exchange
        self.connection_kwargs = connection_kwargs
        self.is_running = False
        self._connection = None
        self._channel = None

    def start(self) -> None:
        if not self._connection or self._connection.is_closed:
            params = pika.URLParameters(self.rabbitmq_url)
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            self._channel.queue_declare(queue=self.queue, durable=False)
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False
        if self._connection and not self._connection.is_closed:
            self._connection.close()
            self._connection = None
            self._channel = None

    def handle_event(self, event: Event) -> None:
        if not self.is_running:
            return

        if not self._connection or self._connection.is_closed:
            self.start()

        message = json.dumps(event.model_dump(), default=str)

        self._channel.basic_publish(
            exchange=self.exchange, routing_key=self.queue, body=message.encode()
        )
