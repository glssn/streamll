"""Redis Streams consumer for StreamLL events."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import urlparse

from streamll.consumer.base import BaseConsumer, ConsumerConfig
from streamll.models import StreamllEvent, generate_event_id


class RedisStreamConsumer(BaseConsumer):
    """Consumer for reading StreamLL events from Redis Streams.

    Provides high-level interface for consuming events with:
    - Type-safe event handlers
    - Automatic deserialization
    - Consumer groups support
    - Checkpointing
    - Batch processing
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        consumer_group: str | None = None,
        consumer_name: str | None = None,
        batch_size: int = 10,
        block_ms: int = 1000,
        start_id: str = "$",  # $ = only new messages, 0 = from beginning
        config: ConsumerConfig | None = None,
    ):
        """Initialize Redis stream consumer.

        Args:
            redis_url: Redis connection URL
            stream_key: Redis stream key to consume from
            consumer_group: Consumer group name (for distributed processing)
            consumer_name: Unique consumer name within group
            batch_size: Max messages to read per batch
            block_ms: Block timeout in milliseconds
            start_id: Starting position in stream
            config: Additional consumer configuration
        """
        super().__init__(config)

        self.redis_url = redis_url
        self.stream_key = stream_key
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer-{generate_event_id(8)}"
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.start_id = start_id

        # Parse Redis URL
        parsed = urlparse(redis_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
        self.password = parsed.password

        self._redis_client = None
        self._last_id = start_id

    def _get_redis_client(self):
        """Get or create Redis client.

        Lazy import to avoid requiring redis for core package.
        """
        if self._redis_client is None:
            try:
                import redis
            except ImportError:
                raise ImportError(
                    "Redis support not installed. "
                    "Install with: pip install streamll[redis-consumer]"
                ) from None

            self._redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )

        return self._redis_client

    async def start(self) -> None:
        """Start the consumer and create consumer group if needed."""
        client = self._get_redis_client()

        # Test connection
        try:
            client.ping()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

        # Create consumer group if specified
        if self.consumer_group:
            try:
                client.xgroup_create(
                    name=self.stream_key,
                    groupname=self.consumer_group,
                    id="0",  # Start from beginning
                    mkstream=True,  # Create stream if doesn't exist
                )
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    # Group already exists, that's fine
                    pass
                else:
                    raise

        self._running = True

    async def stop(self) -> None:
        """Stop the consumer and close connections."""
        self._running = False
        if self._redis_client:
            self._redis_client.close()
            self._redis_client = None

    async def consume_one(self) -> StreamllEvent | None:
        """Consume a single event from Redis stream.

        Returns:
            Next event or None if no events available
        """
        events = await self.consume_batch(max_events=1)
        return events[0] if events else None

    async def consume_batch(self, max_events: int | None = None) -> list[StreamllEvent]:  # noqa: C901
        """Consume a batch of events from Redis stream.

        Args:
            max_events: Maximum events to consume (default: batch_size)

        Returns:
            List of events
        """
        if not self._running:
            return []

        client = self._get_redis_client()
        max_events = max_events or self.batch_size
        events = []

        try:
            if self.consumer_group:
                # Read as part of consumer group
                messages = client.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.stream_key: ">"},  # > means undelivered messages
                    count=max_events,
                    block=self.block_ms,
                )
            else:
                # Simple read without consumer group
                messages = client.xread(
                    streams={self.stream_key: self._last_id},
                    count=max_events,
                    block=self.block_ms,
                )

            # Process messages
            for _stream_name, stream_messages in messages:
                for message_id, data in stream_messages:
                    try:
                        # Extract event data
                        event_json = data.get("event", data)
                        if isinstance(event_json, str):
                            event_dict = json.loads(event_json)
                        else:
                            event_dict = event_json

                        # Create typed event
                        event = StreamllEvent(**event_dict)
                        events.append(event)

                        # Acknowledge if using consumer group
                        if self.consumer_group:
                            client.xack(self.stream_key, self.consumer_group, message_id)

                        # Update last ID for simple reading
                        self._last_id = message_id

                    except Exception:
                        if self.config.on_validation_error == "raise":
                            raise
                        elif self.config.on_validation_error == "log":
                            pass
                        # Continue with next message

        except Exception as e:
            if "NOGROUP" in str(e):
                raise ValueError(
                    f"Consumer group '{self.consumer_group}' does not exist. "
                    "It should have been created on start()."
                ) from e
            raise

        return events

    def consume_sync(self) -> StreamllEvent:
        """Synchronous consume for simpler use cases.

        Returns:
            Next event (blocks until available)
        """
        loop = asyncio.new_event_loop()
        try:
            while True:
                event = loop.run_until_complete(self.consume_one())
                if event:
                    return event
                # Small sleep to prevent busy loop
                loop.run_until_complete(asyncio.sleep(0.01))
        finally:
            loop.close()

    def iter_events(self, max_events: int | None = None):
        """Iterator interface for consuming events.

        Args:
            max_events: Maximum events to consume (None = infinite)

        Yields:
            StreamllEvent instances

        Example:
            for event in consumer.iter_events():
                print(f"Got event: {event.event_type}")
        """
        count = 0
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.start())

            while self._running and (max_events is None or count < max_events):
                events = loop.run_until_complete(self.consume_batch())
                for event in events:
                    yield event
                    count += 1
                    if max_events and count >= max_events:
                        break

                if not events:
                    # No events, small sleep
                    loop.run_until_complete(asyncio.sleep(0.1))

        finally:
            loop.run_until_complete(self.stop())
            loop.close()
