"""Event consumer using FastStream."""

import os
from typing import Any, Callable

from faststream import FastStream

from streamll.brokers import create_broker
from streamll.models import StreamllEvent


class EventConsumer:
    """FastStream event consumer for streamll."""

    def __init__(
        self, broker_url: str | None = None, target: str | None = None, **broker_kwargs: Any
    ):
        self.broker_url = broker_url or os.getenv("STREAMLL_BROKER_URL")
        self.target = target or os.getenv("STREAMLL_TARGET", "streamll_events")

        if not self.broker_url:
            raise ValueError("broker_url required")

        self._broker = None
        self._app = None
        self._handlers: dict[str, list[Callable]] = {}
        self._dispatcher_registered = False
        self.broker_kwargs = broker_kwargs

    @property
    def broker(self):
        if self._broker is None:
            self._broker = create_broker(self.broker_url, **self.broker_kwargs)
        return self._broker

    @property
    def app(self):
        if self._app is None:
            self._app = FastStream(self.broker)
        return self._app

    def on(self, event_type: str) -> Callable:
        def decorator(func: Callable[[StreamllEvent], Any]) -> Callable:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)

            if not self._dispatcher_registered:
                self._register_dispatcher()
                self._dispatcher_registered = True

            return func

        return decorator

    def _register_dispatcher(self) -> None:
        scheme = self.broker_url.split("://")[0].lower()

        if scheme == "redis":
            from faststream.redis import StreamSub

            @self.broker.subscriber(stream=StreamSub(self.target, last_id="0"))
            async def dispatcher(raw_event: dict) -> None:
                await self._dispatch_event(raw_event)

        elif scheme in ("amqp", "rabbitmq"):

            @self.broker.subscriber(queue=self.target)
            async def dispatcher(raw_event: dict) -> None:
                await self._dispatch_event(raw_event)

        else:

            @self.broker.subscriber(self.target)
            async def dispatcher(raw_event: dict) -> None:
                await self._dispatch_event(raw_event)

    async def _dispatch_event(self, raw_event: dict) -> None:
        event_type = raw_event.get("event_type")
        if event_type and event_type in self._handlers:
            event = StreamllEvent(**raw_event)
            for handler in self._handlers[event_type]:
                await handler(event)
    
    async def _dispatch_event_direct(self, event: StreamllEvent) -> None:
        """Dispatch event when already a StreamllEvent (for Pydantic deserialization)."""
        if event.event_type and event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                await handler(event)

    def subscriber(self, **kwargs: Any) -> Callable:
        scheme = self.broker_url.split("://")[0].lower()
        if not any(k in kwargs for k in ["stream", "queue", "subject"]):
            if scheme == "redis":
                from faststream.redis import StreamSub
                from faststream.redis.parser import BinaryMessageFormatV1
                
                kwargs["stream"] = StreamSub(self.target, last_id="$")
                if "message_format" not in kwargs:
                    kwargs["message_format"] = BinaryMessageFormatV1
            elif scheme in ("amqp", "rabbitmq"):
                kwargs["queue"] = self.target

        return self.broker.subscriber(**kwargs)

    async def start(self) -> None:
        """Start the broker."""
        await self.broker.start()

    async def stop(self) -> None:
        """Stop the broker."""
        await self.broker.stop()

    async def run(self) -> None:
        """Run the FastStream app."""
        await self.app.run()
