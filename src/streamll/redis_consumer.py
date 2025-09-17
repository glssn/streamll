import asyncio
import json
from typing import Any, Callable

import redis

from streamll.models import Event


class RedisEventConsumer:
    def __init__(
        self,
        broker_url: str,
        target: str,
        **connection_kwargs: Any,
    ):
        self.broker_url = broker_url
        self.stream_key = target
        self.connection_kwargs = connection_kwargs
        self._redis = None
        self._handlers: dict[str, list[Callable]] = {}
        self._running = False
        self._last_id = "0-0"

    @property
    def redis(self):
        if self._redis is None:
            self._redis = redis.Redis.from_url(self.broker_url, **self.connection_kwargs)
        return self._redis

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

    async def run(self) -> None:
        self._running = True

        while self._running:
            if self.redis.exists(self.stream_key):
                messages = self.redis.xread(
                    {self.stream_key: self._last_id},
                    block=100,
                    count=10,
                )

                if messages:
                    for _, msgs in messages:
                        for msg_id, fields in msgs:
                            self._last_id = msg_id.decode()

                            if b"message" in fields:
                                event_data = json.loads(fields[b"message"])
                                await self._dispatch_event(event_data)

                await asyncio.sleep(0.01)  # Allow cancellation
            else:
                await asyncio.sleep(0.1)

    async def stop(self) -> None:
        self._running = False
        if self._redis:
            self._redis.close()
            self._redis = None

