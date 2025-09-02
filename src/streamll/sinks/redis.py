from typing import Any

from streamll.brokers import create_broker
from streamll.models import StreamllEvent


class RedisSink:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        **broker_kwargs: Any,
    ):
        self._broker = create_broker(redis_url, **broker_kwargs)
        self.stream_key = stream_key
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
            event_dict = event.model_dump()
            await self._broker.publish(event_dict, stream=self.stream_key)
