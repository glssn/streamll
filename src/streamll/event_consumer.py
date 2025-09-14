import os
from typing import Any, Callable

from faststream import FastStream

from streamll.models import Event


class EventConsumer:
    def __init__(
        self, broker_url: str | None = None, target: str | None = None, **broker_kwargs: Any
    ):
        url = broker_url or os.getenv("STREAMLL_BROKER_URL")
        if not url:
            raise ValueError("broker_url required")

        self.broker_url: str = url
        self.target = target or os.getenv("STREAMLL_TARGET", "streamll_events")

        self._broker = None
        self._app = None
        self._handlers: dict[str, list[Callable]] = {}
        self._dispatcher_registered = False
        self.broker_kwargs = broker_kwargs

    @property
    def broker(self):
        if self._broker is None:
            from urllib.parse import urlparse

            scheme = urlparse(self.broker_url).scheme.lower()

            if scheme == "redis":
                from faststream.redis import RedisBroker

                self._broker = RedisBroker(self.broker_url, **self.broker_kwargs)
            elif scheme in ("amqp", "rabbitmq"):
                from faststream.rabbit import RabbitBroker

                self._broker = RabbitBroker(self.broker_url, **self.broker_kwargs)
            else:
                raise ValueError(
                    f"Unsupported broker URL scheme: {scheme}. "
                    f"Supported: redis://, amqp://, rabbitmq://"
                )

        return self._broker

    @property
    def app(self):
        if self._app is None:
            self._app = FastStream(self.broker)
        return self._app

    def on(self, event_type: str) -> Callable:
        def decorator(func: Callable[[Event], Any]) -> Callable:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)

            if not self._dispatcher_registered:
                self._register_dispatcher()
                self._dispatcher_registered = True

            return func

        return decorator

    def _register_dispatcher(self) -> None:
        from urllib.parse import urlparse

        scheme = urlparse(self.broker_url).scheme.lower()

        if scheme == "redis":
            from faststream.redis import StreamSub

            @self.broker.subscriber(stream=StreamSub(self.target, last_id="0"))
            async def dispatcher(raw_event: dict) -> None:
                await self._dispatch_event(raw_event)

        elif scheme in ("amqp", "rabbitmq"):

            @self.broker.subscriber(queue=self.target)
            async def dispatcher(raw_event: dict) -> None:
                await self._dispatch_event(raw_event)

    async def _dispatch_event(self, raw_event: dict) -> None:
        event_type = raw_event.get("event_type")
        if event_type and event_type in self._handlers:
            event = Event(**raw_event)  # type: ignore[missing-argument]
            for handler in self._handlers[event_type]:
                await handler(event)

    async def _dispatch_event_direct(self, event: Event) -> None:
        if event.event_type and event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                await handler(event)

    def subscriber(self, **kwargs: Any) -> Callable:
        from urllib.parse import urlparse

        scheme = urlparse(self.broker_url).scheme.lower()
        if not any(k in kwargs for k in ["stream", "queue", "subject"]):
            if scheme == "redis":
                from faststream.redis import StreamSub

                kwargs["stream"] = StreamSub(self.target, last_id="$")
            elif scheme in ("amqp", "rabbitmq"):
                kwargs["queue"] = self.target

        return self.broker.subscriber(**kwargs)

    async def start(self) -> None:
        await self.broker.start()

    async def stop(self) -> None:
        await self.broker.stop()

    async def run(self) -> None:
        await self.app.run()
