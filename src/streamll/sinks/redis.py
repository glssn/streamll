import json
from typing import Any

import redis

from streamll.models import Event


class RedisSink:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        max_stream_length: int = 10000,
        **connection_kwargs: Any,
    ):
        self.redis_url = redis_url
        self.stream_key = stream_key
        self.max_stream_length = max_stream_length
        self.connection_kwargs = connection_kwargs
        self.is_running = False
        self._connection_pool = None
        self._redis = None

    def start(self) -> None:
        if not self._connection_pool:
            self._connection_pool = redis.ConnectionPool.from_url(
                self.redis_url, **self.connection_kwargs
            )
            self._redis = redis.Redis(connection_pool=self._connection_pool)
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False
        if self._connection_pool:
            self._connection_pool.disconnect()
            self._connection_pool = None
            self._redis = None

    def handle_event(self, event: Event) -> None:
        if not self.is_running:
            return

        if not self._redis:
            self.start()

        event_dict = event.model_dump()
        message_json = json.dumps(event_dict, default=str)

        self._redis.xadd(
            name=self.stream_key,
            fields={"message": message_json},
            maxlen=self.max_stream_length,
            approximate=True,
        )
