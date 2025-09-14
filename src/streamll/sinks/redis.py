from typing import Any

from faststream.redis import RedisBroker

from streamll.models import Event


class RedisSink:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        **broker_kwargs: Any,
    ):
        self.broker = RedisBroker(redis_url, **broker_kwargs)
        self.stream_key = stream_key
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

        event_dict = event.model_dump()
        await self.broker.publish(event_dict, stream=self.stream_key)
