import json
from typing import Any, Callable

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from streamll.models import Event


class RabbitMQEventConsumer:
    def __init__(
        self,
        broker_url: str,
        target: str,
        **connection_kwargs: Any,
    ):
        self.broker_url = broker_url
        self.queue = target
        self.connection_kwargs = connection_kwargs
        self._connection = None
        self._channel = None
        self._queue = None
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False

    async def _get_connection(self):
        if not self._connection or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(
                self.broker_url, **self.connection_kwargs
            )
            self._channel = await self._connection.channel()
            self._queue = await self._channel.declare_queue(name=self.queue, durable=False)
        return self._connection, self._channel, self._queue

    def on(self, event_type: str) -> Callable:
        def decorator(func: Callable[[Event], Any]) -> Callable:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func

        return decorator

    async def _dispatch_event(self, event_data: dict) -> None:
        event_type = event_data.get("event_type")
        if event_type and event_type in self._handlers:
            event = Event(**event_data)  # type: ignore[misc]
            for handler in self._handlers[event_type]:
                await handler(event)

    async def _message_callback(self, message: AbstractIncomingMessage):
        async with message.process():
            event_data = json.loads(message.body.decode())
            await self._dispatch_event(event_data)

    async def run(self) -> None:
        self._running = True
        _, _, queue = await self._get_connection()
        if queue:
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    if not self._running:
                        break
                    await self._message_callback(message)

    async def stop(self) -> None:
        self._running = False
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._queue = None
