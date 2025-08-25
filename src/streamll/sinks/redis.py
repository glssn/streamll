"""Redis sink for streaming events to Redis Streams."""

import json
import logging
from urllib.parse import urlparse

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink

logger = logging.getLogger(__name__)


class RedisSink(BaseSink):
    """Writes events to Redis Streams with production-ready features."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        buffer_size: int = 10000,
        batch_size: int = 100,
        client=None,  # For test injection
    ):
        """Initialize Redis sink.

        Args:
            url: Redis connection URL
            stream_key: Redis stream key for events
            buffer_size: Maximum events to buffer
            batch_size: Events per batch write
            client: Optional Redis client for testing
        """
        super().__init__(
            buffer_size=buffer_size,
            batch_size=batch_size,
            flush_interval=1.0,
            failure_threshold=3,
            recovery_timeout=30.0,
        )

        self.url = url
        self.stream_key = stream_key

        # Parse Redis URL
        parsed = urlparse(url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
        self.password = parsed.password
        self.ssl = parsed.scheme == "rediss"

        self._redis_client = client  # Use injected client if provided

    def start(self) -> None:
        """Start the Redis sink and establish connection."""
        super().start()

        # Create Redis client if not injected
        if self._redis_client is None:
            try:
                import redis
            except ImportError:
                raise ImportError(
                    "Redis not installed. Install with: pip install streamll[redis-producer]"
                ) from None

            self._redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                ssl=self.ssl,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

        # Test connection
        try:
            self._redis_client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")

    def stop(self) -> None:
        """Stop the sink and close connection."""
        super().stop()

        if self._redis_client:
            try:
                self._redis_client.close()
                logger.info("Closed Redis connection")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")

    def _write_batch(self, events: list[StreamllEvent]) -> None:
        """Write batch of events to Redis Stream.

        Args:
            events: Events to write

        Raises:
            Exception: If write fails
        """
        if not self._redis_client:
            raise RuntimeError("Redis client not initialized")

        # Use pipeline for batched writes (82x speedup)
        pipe = self._redis_client.pipeline()

        for event in events:
            # Serialize event to dict
            event_dict = event.model_dump()

            # Convert datetime to ISO format
            if "timestamp" in event_dict:
                event_dict["timestamp"] = event_dict["timestamp"].isoformat()

            # Add to stream with automatic ID
            pipe.xadd(self.stream_key, {"event": json.dumps(event_dict)})

        # Execute pipeline
        results = pipe.execute()

        # Verify all writes succeeded
        if not all(results):
            raise RuntimeError(f"Failed to write {len([r for r in results if not r])} events")

        logger.debug(f"Wrote {len(events)} events to Redis stream")

    def get_stream_info(self) -> dict:
        """Get information about the Redis stream.

        Returns:
            Stream info including length and consumer groups
        """
        if not self._redis_client:
            return {"error": "Not connected"}

        try:
            info = self._redis_client.xinfo_stream(self.stream_key)
            groups = self._redis_client.xinfo_groups(self.stream_key)
            return {
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "consumer_groups": len(groups),
            }
        except Exception as e:
            return {"error": str(e)}
