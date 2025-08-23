"""Redis sink for streaming events to Redis Streams.

Provides production-ready event streaming with connection resilience,
buffering, and circuit breaker patterns.
"""

import json
import logging
import time
from collections import deque
from urllib.parse import urlparse

import redis

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink
from streamll.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class RedisSink(BaseSink):
    """Writes events to Redis Streams with buffering and circuit breaker."""

    def __init__(
        self,
        url: str = "redis://localhost:6379",
        stream_key: str = "streamll_events",
        buffer_size: int = 10000,
        max_batch_size: int = 100,
        flush_interval: float = 1.0,
        circuit_breaker: bool = True,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        consumer_group: str | None = None,
        consumer_name: str | None = None,
        max_stream_length: int | None = None,
        approximate_trimming: bool = True,
        trim_strategy: str = "MAXLEN",
        buffer_overflow_strategy: str = "drop_oldest",
        client: redis.Redis | None = None,  # For test injection
    ):
        super().__init__(
            buffer_size=buffer_size, batch_size=max_batch_size, flush_interval=flush_interval
        )

        self.url = url
        self.stream_key = stream_key
        self.circuit_breaker_enabled = circuit_breaker
        self.buffer_overflow_strategy = buffer_overflow_strategy

        # Parse Redis URL
        parsed = urlparse(url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0
        self.password = parsed.password
        self.ssl = parsed.scheme == "rediss" or ("ssl=true" in url)

        # Redis client
        self._redis_client: redis.Redis | None = client  # Use injected client if provided

        # Local buffer for resilience
        self._local_buffer: deque[StreamllEvent] = deque(
            maxlen=buffer_size if buffer_overflow_strategy == "drop_oldest" else None
        )

        # Circuit breaker
        if circuit_breaker:
            self._circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        else:
            self._circuit_breaker = None

        # Consumer group configuration
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name

        # Stream configuration
        self.max_stream_length = max_stream_length
        self.approximate_trimming = approximate_trimming
        self.trim_strategy = trim_strategy

        # Retry configuration
        self._retry_count = 0
        self._max_retry_delay = 30.0

    def start(self) -> None:
        """Start the Redis sink and establish connection."""
        self.is_running = True

        # Create Redis client if not injected
        if self._redis_client is None:
            self._redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                ssl=self.ssl,
                # TODO: ARCHITECTURE CONSISTENCY - decode_responses=True forces string decoding
                # RabbitMQ sink handles binary data differently, should this be configurable?
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=10,
            )

        # Test connection
        try:
            self._redis_client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")

            # Create consumer group if specified
            if self._consumer_group:
                self._create_consumer_group()
        except redis.ConnectionError as e:
            logger.warning(f"Failed to connect to Redis: {e}. Will retry on first event.")

    def stop(self) -> None:
        """Stop the sink and flush remaining events."""
        if not self.is_running:
            return

        # Flush any remaining buffered events
        self._flush_buffer()

        # Close Redis connection
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception as e:
                # TODO: ARCHITECTURE CONSISTENCY - RabbitMQ sink now logs cleanup errors differently
                # Consider standardizing cleanup error handling across all sinks
                logger.error(f"Error closing Redis connection: {e}")

        self.is_running = False
        logger.info("Redis sink stopped")

    def handle_event(self, event: StreamllEvent) -> None:
        """Handle a single event by writing to Redis or buffering.

        Args:
            event: Event to process
        """
        if not self.is_running:
            return

        # Check circuit breaker
        if self._circuit_breaker and not self._circuit_breaker.should_attempt():
            self._buffer_event(event)
            return

        # Try to write to Redis
        try:
            self._write_to_redis(event)

            # Success - reset circuit breaker and retry count
            if self._circuit_breaker:
                self._circuit_breaker.record_success()
            self._retry_count = 0

            # Try to flush any buffered events
            if self._local_buffer:
                self._flush_buffer()

        except redis.ConnectionError as e:
            logger.warning(f"Failed to write to Redis: {e}")

            # Record failure
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()

            # Buffer the event
            self._buffer_event(event)

    def flush(self) -> None:
        """Flush buffered events to Redis."""
        self._flush_buffer()

    def _write_to_redis(self, event: StreamllEvent) -> None:
        """Write event to Redis stream.

        Args:
            event: Event to write
        """
        if not self._redis_client:
            raise redis.ConnectionError("Redis client not initialized")

        # Serialize event
        event_data = self._serialize_event(event)

        # Prepare XADD arguments
        xadd_args = {"name": self.stream_key, "fields": {"event": event_data}}

        # Add stream trimming if configured
        if self.max_stream_length:
            xadd_args["maxlen"] = self.max_stream_length
            xadd_args["approximate"] = self.approximate_trimming

        # TODO: Consider using Redis pipelines for batch operations to improve performance
        # Write to stream
        stream_id = self._redis_client.xadd(**xadd_args)
        logger.debug(f"Wrote event to Redis stream: {stream_id}")

    def _serialize_event(self, event: StreamllEvent) -> str:
        event_dict = event.model_dump(mode="json")

        # Convert datetime to ISO format
        if "timestamp" in event_dict and isinstance(event_dict["timestamp"], str):
            # Already serialized by Pydantic
            pass
        elif "timestamp" in event_dict:
            event_dict["timestamp"] = event_dict["timestamp"].isoformat()

        return json.dumps(event_dict, separators=(",", ":"))

    def _buffer_event(self, event: StreamllEvent) -> None:
        # TODO: ARCHITECTURE CONSISTENCY - Buffer overflow strategies only exist in Redis sink
        # RabbitMQ sink doesn't have configurable overflow strategies - should they be consistent?
        # Current approach is complex with 3 strategies: drop_oldest, drop_newest, raise_error
        if (
            self.buffer_overflow_strategy == "raise_error"
            and len(self._local_buffer) >= self.buffer_size
        ):
            raise BufferError(f"Local buffer full ({self.buffer_size} events)")

        if (
            self.buffer_overflow_strategy == "drop_newest"
            and len(self._local_buffer) >= self.buffer_size
        ):
            logger.warning("Local buffer full, dropping new event")
            return

        # For drop_oldest, deque with maxlen handles it automatically
        self._local_buffer.append(event)
        logger.debug(f"Buffered event locally. Buffer size: {len(self._local_buffer)}")

    def _flush_buffer(self) -> None:
        """Attempt to flush buffered events to Redis using pipeline batching."""
        if not self._local_buffer or not self._redis_client:
            return

        # Create a copy of events to flush to avoid mutating buffer during iteration
        events_to_flush = list(self._local_buffer)

        # Use Redis pipeline for batch operations to improve performance
        try:
            flushed_count = self._flush_with_pipeline(events_to_flush)
        except redis.ConnectionError:
            # Pipeline failed, fall back to individual writes
            logger.warning("Pipeline batch failed, falling back to individual writes")
            flushed_count = self._flush_individually(events_to_flush)

        # Only remove successfully flushed events from buffer
        for _ in range(flushed_count):
            self._local_buffer.popleft()

        if flushed_count > 0:
            logger.info(f"Flushed {flushed_count} buffered events to Redis")

    def _flush_with_pipeline(self, events: list[StreamllEvent]) -> int:
        """Flush events using Redis pipeline for better performance.

        Args:
            events: List of events to flush

        Returns:
            Number of successfully flushed events
        """
        if not events:
            return 0

        # Create Redis pipeline for batch operations
        pipeline = self._redis_client.pipeline()

        # Add all events to pipeline
        for event in events:
            event_data = self._serialize_event(event)
            xadd_args = {"name": self.stream_key, "fields": {"event": event_data}}

            # Add stream trimming if configured
            if self.max_stream_length:
                xadd_args["maxlen"] = self.max_stream_length
                xadd_args["approximate"] = self.approximate_trimming

            pipeline.xadd(**xadd_args)

        # Execute pipeline atomically
        results = pipeline.execute()

        # All operations in pipeline either succeed or fail together
        logger.debug(f"Pipeline executed {len(results)} XADD operations")
        return len(events)

    def _flush_individually(self, events: list[StreamllEvent]) -> int:
        """Fallback to flush events individually when pipeline fails.

        Args:
            events: List of events to flush

        Returns:
            Number of successfully flushed events
        """
        flushed_count = 0

        for event in events:
            try:
                self._write_to_redis(event)
                flushed_count += 1
            except redis.ConnectionError:
                # Connection failed - stop flushing and leave remaining events in buffer
                break

        return flushed_count

    def _create_consumer_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        if not self._redis_client or not self._consumer_group:
            return

        try:
            # Try to create consumer group
            self._redis_client.xgroup_create(
                name=self.stream_key,
                groupname=self._consumer_group,
                id="0",  # Start from beginning
                mkstream=True,  # Create stream if doesn't exist
            )
            logger.info(f"Created consumer group: {self._consumer_group}")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                # Group already exists
                logger.debug(f"Consumer group already exists: {self._consumer_group}")
            else:
                raise

    def _wait_for_redis_connection(self, max_retries: int = 10, delay: float = 0.5) -> bool:
        """Wait for Redis connection to be available.

        Args:
            max_retries: Maximum connection attempts
            delay: Initial delay between attempts

        Returns:
            True if connected, False otherwise
        """
        current_delay = delay  # Use local variable to avoid mutating parameter

        for _ in range(max_retries):
            try:
                if self._redis_client:
                    self._redis_client.ping()
                    return True
            except redis.ConnectionError:
                time.sleep(current_delay)
                # Use local variable for exponential backoff
                current_delay = min(current_delay * 2, self._max_retry_delay)

        return False

    @property
    def failures(self) -> int:
        """Get current failure count for architecture consistency with RabbitMQ sink."""
        return self._circuit_breaker.failure_count if self._circuit_breaker else 0
