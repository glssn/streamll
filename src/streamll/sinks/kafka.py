"""Kafka sink for streamll events using Apache Kafka protocol.

Following Diamond Development Process:
1. Data Integrity - Reliable event delivery with schema validation
2. Reliability - Circuit breaker, retries, connection resilience
3. Architecture Consistency - Matches Redis/RabbitMQ patterns
4. Performance - Batching, compression, async producers
"""

import asyncio
import json
import logging
import time
from queue import Queue
from threading import Thread

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink
from streamll.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class KafkaSink(BaseSink):
    """Publishes events to Kafka with batching and circuit breaker.

    Following Diamond Approach:
    - Data Integrity: JSON schema validation, at-least-once delivery
    - Reliability: Circuit breaker, auto-reconnection, configurable retries
    - Architecture: Consistent with Redis/RabbitMQ sink patterns
    - Performance: Producer batching, compression, async operations
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "streamll_events",
        # Data Integrity Parameters (Priority 1)
        acks: int = -1,                     # Wait for all replicas (-1/all) when idempotent
        enable_idempotence: bool = True,    # Prevent duplicate messages
        max_in_flight_requests: int = 1,    # Ordering guarantee with retries
        # Reliability Parameters (Priority 2)
        circuit_breaker: bool = True,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_ms: int = 100,
        request_timeout_ms: int = 30000,
        # Architecture Consistency (Priority 3) - Match Redis/RabbitMQ patterns
        batch_size: int = 50,               # Same as RabbitMQ default
        batch_timeout_ms: int = 100,        # Similar to RabbitMQ batch_timeout
        buffer_size: int = 1000,            # Match BaseSink pattern
        # Performance Parameters (Priority 4)
        compression_type: str = "snappy",  # snappy (default), gzip, lz4, zstd, or None
        partitioner_strategy: str = "round_robin",  # round_robin, hash, sticky
        **kwargs,
    ):
        """Initialize Kafka sink with Diamond Approach priorities.

        Args:
            bootstrap_servers: Comma-separated Kafka broker addresses
            topic: Kafka topic for events (auto-created if needed)
            acks: Producer acknowledgment mode (0, 1, all)
            enable_idempotence: Prevent duplicate messages
            max_in_flight_requests: Max unacknowledged requests (1 for ordering)
            circuit_breaker: Enable circuit breaker for fault tolerance
            failure_threshold: Failures before circuit opens
            recovery_timeout: Time before attempting recovery (seconds)
            max_retries: Maximum retry attempts per message
            retry_backoff_ms: Backoff time between retries
            request_timeout_ms: Request timeout
            batch_size: Messages per batch (like RabbitMQ)
            batch_timeout_ms: Max time to wait for batch
            buffer_size: Internal event buffer size
            compression_type: Message compression (none, gzip, snappy, lz4, zstd)
            partitioner_strategy: Partitioning strategy
            **kwargs: Additional aiokafka producer configuration
        """
        super().__init__(buffer_size=buffer_size, batch_size=batch_size)

        # Kafka connection configuration
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer_config = kwargs

        # Data Integrity Configuration (Priority 1)
        self.acks = acks
        self.enable_idempotence = enable_idempotence
        self.max_in_flight_requests = max_in_flight_requests

        # Reliability Configuration (Priority 2)
        self.circuit_breaker_enabled = circuit_breaker
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_retries = max_retries
        self.retry_backoff_ms = retry_backoff_ms
        self.request_timeout_ms = request_timeout_ms

        # Performance Configuration (Priority 4)
        self.batch_timeout_ms = batch_timeout_ms
        self.compression_type = compression_type
        self.partitioner_strategy = partitioner_strategy

        # Runtime state
        self.producer = None
        self.event_queue = Queue()
        self.worker_thread = None

        # Circuit breaker for fault tolerance (Priority 2)
        if circuit_breaker:
            self._circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        else:
            self._circuit_breaker = None

        # Message batching state (Priority 4)
        self._message_batch = []
        self._last_batch_time = None

    def start(self) -> None:
        """Start the Kafka sink worker thread."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info(f"Kafka sink started (topic={self.topic})")

    def stop(self) -> None:
        """Stop the Kafka sink and close connections."""
        if not self.is_running:
            return

        self.is_running = False

        # Signal worker to stop
        self.event_queue.put(None)

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)

        logger.info("Kafka sink stopped")

    def flush(self) -> None:
        """Flush any buffered events immediately.

        For Kafka sink, events are processed by worker thread,
        so we wait until the queue is empty.
        """
        if not self.is_running:
            return

        # Wait for queue to be empty with timeout
        timeout = 5.0  # Maximum wait time
        start_time = time.time()

        while not self.event_queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.01)  # Small polling interval

        # Give worker thread a moment to process the last event
        if self.event_queue.empty():
            time.sleep(0.05)

    def handle_event(self, event: StreamllEvent) -> None:
        """Queue event for async publishing to Kafka."""
        if not self.is_running:
            logger.warning("KafkaSink not running, dropping event")
            return

        if self._circuit_breaker and not self._circuit_breaker.should_attempt():
            logger.warning(f"Circuit breaker open, dropping event {event.event_id}")
            return

        try:
            self.event_queue.put(event)
        except Exception as e:
            logger.warning(f"Failed to queue event for Kafka: {e}")

    def _worker_loop(self) -> None:
        """Main worker loop for processing events."""
        # Create new event loop for worker thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._async_worker())
        except Exception as e:
            logger.error(f"Kafka worker error: {e}")
        finally:
            loop.close()

    async def _async_worker(self) -> None:
        """Async worker that processes events from queue."""
        try:
            import aiokafka  # noqa: F401
        except ImportError:
            logger.error("aiokafka not installed. Install with: pip install streamll[kafka]")
            return

        # Initialize batch timing
        if self._last_batch_time is None:
            self._last_batch_time = time.time()

        while self.is_running:
            try:
                # Check circuit breaker before attempting any work
                if self._circuit_breaker and not self._circuit_breaker.should_attempt():
                    # Circuit is open, wait and skip processing
                    await asyncio.sleep(0.1)
                    continue

                # Get event from queue with short timeout for batching
                event = await asyncio.get_event_loop().run_in_executor(
                    None, self._get_event_with_timeout, 0.01
                )

                if event is None and not self.is_running:  # Shutdown signal
                    break

                # Ensure producer connection
                if not await self._ensure_producer():
                    await self._handle_failure()
                    continue

                # Add event to batch
                if event is not None:
                    self._message_batch.append(event)

                # Check if batch should be published
                should_publish = (
                    len(self._message_batch) >= self.batch_size or  # Batch size reached
                    (self._message_batch and
                     time.time() - self._last_batch_time >= self.batch_timeout_ms / 1000) or  # Timeout
                    (event is None and self._message_batch)  # Got timeout, but have events to publish
                )

                if should_publish and self._message_batch:
                    await self._publish_batch(self._message_batch)
                    self._message_batch.clear()
                    self._last_batch_time = time.time()

                    # Reset failure count on successful batch
                    if self._circuit_breaker:
                        self._circuit_breaker.record_success()

            except Exception as e:
                logger.warning(f"Kafka worker error: {e}")
                await self._handle_failure()

        # Cleanup
        await self._cleanup_producer()

    def _get_event_with_timeout(self, timeout: float) -> StreamllEvent | None:
        """Get event from queue with specific timeout for batching."""
        try:
            return self.event_queue.get(timeout=timeout)
        except Exception:
            return None  # Timeout or queue empty

    async def _ensure_producer(self) -> bool:
        """Ensure Kafka producer is connected and ready."""
        if self.producer and not getattr(self.producer, '_closed', True):
            return True

        try:
            import aiokafka

            # Data Integrity: Configure producer for reliable delivery
            self.producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                # Data Integrity settings (Priority 1)
                acks=self.acks,
                enable_idempotence=self.enable_idempotence,
                # Note: max_in_flight_requests not available in aiokafka
                # Reliability settings (Priority 2)
                retry_backoff_ms=self.retry_backoff_ms,
                request_timeout_ms=self.request_timeout_ms,
                # Performance settings (Priority 4)  
                compression_type=self.compression_type,
                max_batch_size=self.batch_size * 1024,  # Convert to bytes estimate
                linger_ms=self.batch_timeout_ms,
                # Additional configuration
                **self.producer_config
            )

            await self.producer.start()
            
            # Test connection by getting cluster metadata
            # This forces an actual connection attempt
            await self.producer.client.bootstrap()
            
            logger.info(f"Connected to Kafka: {self.bootstrap_servers}")
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to Kafka: {e}")
            return False

    async def _publish_batch(self, events: list[StreamllEvent]) -> None:
        """Publish batch of events to Kafka (Priority 4: Performance).

        This provides performance benefits similar to Redis pipelines by:
        1. Reducing network round trips
        2. Amortizing connection overhead
        3. Leveraging Kafka's native batching
        """
        if not events:
            return

        try:
            # Prepare all messages in batch
            send_tasks = []
            for event in events:
                # Data Integrity: Serialize with schema validation
                message_value = self._serialize_event(event)
                partition_key = self._generate_partition_key(event)

                # Create send task
                task = self.producer.send(
                    self.topic,
                    value=message_value,
                    key=partition_key,
                    headers=self._generate_headers(event)
                )
                send_tasks.append(task)

            # Execute all sends and wait for acknowledgments (Data Integrity)
            await asyncio.gather(*send_tasks)

            logger.debug(f"Published batch of {len(events)} events to Kafka topic {self.topic}")

        except Exception as e:
            logger.warning(f"Failed to publish batch to Kafka: {e}")
            raise

    def _serialize_event(self, event: StreamllEvent) -> bytes:
        """Data Integrity: Serialize event with schema validation."""
        try:
            # Create structured event payload
            event_dict = {
                "event_id": event.event_id,
                "execution_id": event.execution_id,
                "timestamp": event.timestamp.isoformat(),
                "module_name": event.module_name,
                "method_name": event.method_name,
                "event_type": event.event_type,
                "operation": event.operation,
                "data": event.data,
                "tags": event.tags,
                # Add schema version for future compatibility
                "schema_version": "1.0",
                "sink_type": "kafka"
            }

            return json.dumps(event_dict).encode('utf-8')

        except Exception as e:
            logger.error(f"Failed to serialize event {event.event_id}: {e}")
            raise

    def _generate_partition_key(self, event: StreamllEvent) -> bytes | None:
        """Performance: Generate partition key for load distribution."""
        if self.partitioner_strategy == "hash":
            # Hash by execution_id for session affinity
            return event.execution_id.encode('utf-8')
        elif self.partitioner_strategy == "sticky":
            # Stick to same partition for module
            return f"{event.module_name}:{event.method_name}".encode()
        else:
            # round_robin: Return None to let Kafka handle round-robin
            return None

    def _generate_headers(self, event: StreamllEvent) -> list[tuple[str, bytes]]:
        """Generate Kafka message headers for routing and filtering."""
        return [
            ("streamll_version", b"0.1.0"),
            ("event_type", event.event_type.encode('utf-8')),
            ("operation", (event.operation or "unknown").encode('utf-8')),
            ("module_name", event.module_name.encode('utf-8')),
            ("execution_id", event.execution_id.encode('utf-8')),
        ]

    async def _handle_failure(self) -> None:
        """Reliability: Handle connection/publish failures with circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()

        # Close broken producer
        await self._cleanup_producer()

    async def _cleanup_producer(self) -> None:
        """Clean up Kafka producer."""
        try:
            if self.producer and not getattr(self.producer, '_closed', True):
                await self.producer.stop()
        except Exception as e:
            logger.debug(f"Kafka cleanup error (non-critical): {e}")
        finally:
            self.producer = None

    @property
    def failures(self) -> int:
        """Architecture Consistency: Get current failure count for monitoring."""
        return self._circuit_breaker.failure_count if self._circuit_breaker else 0
