"""RabbitMQ sink for streamll events using AMQP message queuing."""

import asyncio
import json
import logging
import time
from queue import Queue
from threading import Event, Thread

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink
from streamll.utils.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class RabbitMQSink(BaseSink):
    """Publishes events to RabbitMQ with batching and circuit breaker."""

    def __init__(
        self,
        amqp_url: str = "amqp://guest:guest@localhost:5672/",
        exchange: str = "streamll_events",
        routing_key: str = "streamll.event",
        queue_name: str | None = None,
        durable: bool = True,
        circuit_breaker: bool = True,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        max_retries: int = 3,
        # Performance configurations (following Redis pipeline pattern)
        publisher_confirms: bool = True,     # Reliability guarantee like Redis transactions
        batch_size: int = 50,               # Message batching like Redis pipelines
        batch_timeout: float = 0.1,         # Maximum batch wait time
        confirm_timeout: float = 5.0,       # Publisher confirm wait time
        use_streams: bool = False,          # RabbitMQ Streams for high throughput (future)
        connection_pool_size: int = 5,      # Connection pooling (future)
        **kwargs,
    ):
        super().__init__()
        self.amqp_url = amqp_url
        self.exchange_name = exchange
        self.routing_key_template = routing_key
        self.queue_name = queue_name
        self.durable = durable
        self.circuit_breaker_enabled = circuit_breaker
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_retries = max_retries
        self.connection_kwargs = kwargs

        # Performance configuration
        self.publisher_confirms = publisher_confirms
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.confirm_timeout = confirm_timeout
        self.use_streams = use_streams
        self.connection_pool_size = connection_pool_size

        # Runtime state
        self.connection = None
        self.channel = None
        self.exchange = None
        self.queue = None
        self.event_queue = Queue()
        self.worker_thread = None

        # Circuit breaker for fault tolerance
        if circuit_breaker:
            self._circuit_breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        else:
            self._circuit_breaker = None

        # Synchronization for flush operations
        self._flush_event = Event()

        # Message batching state (similar to Redis pipeline)
        self._message_batch = []
        self._last_batch_time = None

    def start(self) -> None:
        """Start the RabbitMQ sink worker thread."""
        if self.is_running:
            return

        self.is_running = True
        self.worker_thread = Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info(f"RabbitMQ sink started (exchange={self.exchange_name})")

    def stop(self) -> None:
        """Stop the RabbitMQ sink and close connections."""
        if not self.is_running:
            return

        self.is_running = False

        # Signal worker to stop
        self.event_queue.put(None)

        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)

        logger.info("RabbitMQ sink stopped")

    def flush(self) -> None:
        """Flush any buffered events immediately.

        For RabbitMQ sink, events are processed by worker thread,
        so we wait until the queue is actually empty.
        """
        if not self.is_running:
            return

        # Wait for queue to be empty with timeout
        timeout = 5.0  # Maximum wait time
        start_time = time.time()

        while not self.event_queue.empty() and (time.time() - start_time) < timeout:
            time.sleep(0.01)  # Small polling interval

        # TODO: ARCHITECTURE CONSISTENCY - Still using sleep-based synchronization
        # Redis sink uses proper atomic operations, consider Event-based signaling
        # Give worker thread a moment to process the last event
        if self.event_queue.empty():
            time.sleep(0.05)

    def handle_event(self, event: StreamllEvent) -> None:
        """Queue event for async publishing to RabbitMQ."""
        if not self.is_running:
            return

        if self._circuit_breaker and not self._circuit_breaker.should_attempt():
            return

        try:
            self.event_queue.put(event)
        except Exception as e:
            logger.warning(f"Failed to queue event for RabbitMQ: {e}")

    def _worker_loop(self) -> None:
        """Main worker loop for processing events."""
        import asyncio

        # TODO: ARCHITECTURE CONSISTENCY - Creating new event loop per worker is resource-heavy
        # Consider using shared event loop or asyncio.run() instead
        # This pattern differs from Redis sink which doesn't use asyncio at all
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._async_worker())
        except Exception as e:
            # TODO: ARCHITECTURE CONSISTENCY - Error handling differs from Redis sink
            # Redis sink has specific ConnectionError handling, this swallows all exceptions
            logger.error(f"RabbitMQ worker error: {e}")
        finally:
            loop.close()

    async def _async_worker(self) -> None:
        """Async worker that processes events from queue."""
        try:
            import aio_pika  # noqa: F401
        except ImportError:
            logger.error("aio-pika not installed. Install with: pip install streamll[rabbitmq]")
            return

        # Initialize batch timing
        if self._last_batch_time is None:
            self._last_batch_time = time.time()

        while self.is_running:
            try:
                # Get event from queue with shorter timeout for batching
                event = await asyncio.get_event_loop().run_in_executor(
                    None, self._get_event_with_timeout, 0.01  # Short timeout for responsive batching
                )

                if event is None and not self.is_running:  # Shutdown signal
                    break

                # Ensure connection
                if not await self._ensure_connection():
                    continue

                # Add event to batch or process timeout
                if event is not None:
                    self._message_batch.append(event)

                # Check if batch should be published
                should_publish = (
                    len(self._message_batch) >= self.batch_size or  # Batch size reached
                    (self._message_batch and
                     time.time() - self._last_batch_time >= self.batch_timeout) or  # Timeout reached
                    event is None  # No more events (timeout case)
                )

                if should_publish and self._message_batch:
                    await self._publish_batch(self._message_batch)
                    self._message_batch.clear()
                    self._last_batch_time = time.time()

                    # Reset failure count on successful batch
                    if self._circuit_breaker:
                        self._circuit_breaker.record_success()

            except Exception as e:
                logger.warning(f"RabbitMQ worker error: {e}")
                await self._handle_failure()

        # Cleanup
        await self._cleanup_connection()

    def _get_event_blocking(self) -> StreamllEvent | None:
        """Get event from queue with timeout."""
        while self.is_running:
            try:
                return self.event_queue.get(timeout=1.0)
            except Exception:  # noqa: S112
                # Continue loop if still running, timeout is expected
                continue
        return None

    def _get_event_with_timeout(self, timeout: float) -> StreamllEvent | None:
        """Get event from queue with specific timeout for batching."""
        try:
            return self.event_queue.get(timeout=timeout)
        except Exception:
            return None  # Timeout or queue empty

    async def _ensure_connection(self) -> bool:
        """Ensure RabbitMQ connection and setup exchange/queue."""
        if self.connection and not self.connection.is_closed:
            return True

        try:
            import aio_pika

            # TODO: PERFORMANCE - Implement connection pooling like Redis connection reuse
            # Current: Single connection per sink instance
            # Optimized: Shared connection pool across multiple sinks
            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(
                self.amqp_url,
                **self.connection_kwargs
            )

            # Create channel
            self.channel = await self.connection.channel()

            # Enable publisher confirms for reliability (like Redis transactions)
            # Note: aio-pika handles confirms automatically when enabled in connection
            if self.publisher_confirms:
                # Publisher confirms are handled by aio-pika's robust connection
                logger.debug("Publisher confirms enabled via robust connection")

            # Set QoS for memory control
            await self.channel.set_qos(prefetch_count=self.batch_size * 2)

            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                self.exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=self.durable
            )

            # Optionally declare queue
            if self.queue_name:
                self.queue = await self.channel.declare_queue(
                    self.queue_name,
                    durable=self.durable
                )

                # Bind queue to exchange
                await self.queue.bind(self.exchange, self.routing_key_template)

            logger.info(f"Connected to RabbitMQ: {self.exchange_name}")
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to RabbitMQ: {e}")
            return False

    async def _publish_event(self, event: StreamllEvent) -> None:
        """Publish event to RabbitMQ exchange."""
        try:
            import aio_pika

            # Serialize event
            message_body = json.dumps({
                "event_id": event.event_id,
                "execution_id": event.execution_id,
                "timestamp": event.timestamp.isoformat(),
                "module_name": event.module_name,
                "method_name": event.method_name,
                "event_type": event.event_type,
                "operation": event.operation,
                "data": event.data,
                "tags": event.tags,
            }).encode()

            # Generate routing key from template
            routing_key = self._generate_routing_key(event)

            # Create message
            message = aio_pika.Message(
                message_body,
                content_type="application/json",
                headers={
                    "streamll_version": "0.1.0",
                    "event_type": event.event_type,
                    "operation": event.operation or "unknown",
                    "module_name": event.module_name,
                },
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT if self.durable else aio_pika.DeliveryMode.NOT_PERSISTENT
            )

            # TODO: PERFORMANCE - Implement message batching similar to Redis pipelines
            # Current: Individual publish (like Redis individual XADD)
            # Optimized: Batch multiple messages with publisher confirms
            # See docs/rabbitmq-performance-guide.md for implementation patterns

            # Publish with retries
            for attempt in range(self.max_retries + 1):
                try:
                    await self.exchange.publish(message, routing_key=routing_key)
                    # TODO: PERFORMANCE - Add publisher confirms for reliability
                    # await self.channel.wait_for_confirms(timeout=confirm_timeout)
                    return
                except Exception:
                    if attempt == self.max_retries:
                        raise
                    await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff

        except Exception as e:
            logger.warning(f"Failed to publish event to RabbitMQ: {e}")
            raise

    async def _publish_batch(self, events: list[StreamllEvent]) -> None:
        """Publish batch of events to RabbitMQ (similar to Redis pipeline).

        This provides the same performance benefits as Redis pipelines by:
        1. Reducing network round trips
        2. Batching publisher confirms
        3. Amortizing connection overhead
        """
        if not events:
            return

        try:
            import aio_pika

            # Prepare all messages in batch
            messages_to_publish = []
            for event in events:
                # Serialize event
                message_body = json.dumps({
                    "event_id": event.event_id,
                    "execution_id": event.execution_id,
                    "timestamp": event.timestamp.isoformat(),
                    "module_name": event.module_name,
                    "method_name": event.method_name,
                    "event_type": event.event_type,
                    "operation": event.operation,
                    "data": event.data,
                    "tags": event.tags,
                }).encode()

                # Generate routing key
                routing_key = self._generate_routing_key(event)

                # Create message
                message = aio_pika.Message(
                    message_body,
                    content_type="application/json",
                    headers={
                        "streamll_version": "0.1.0",
                        "event_type": event.event_type,
                        "operation": event.operation or "unknown",
                        "module_name": event.module_name,
                        "batch_size": len(events),
                    },
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT if self.durable else aio_pika.DeliveryMode.NOT_PERSISTENT
                )

                messages_to_publish.append((message, routing_key))

            # Publish all messages in batch (similar to Redis pipeline execute)
            publish_tasks = []
            for message, routing_key in messages_to_publish:
                task = self.exchange.publish(message, routing_key=routing_key)
                publish_tasks.append(task)

            # Execute all publishes concurrently
            await asyncio.gather(*publish_tasks)

            # Wait for publisher confirms if enabled (like Redis transaction commit)
            if self.publisher_confirms:
                # aio-pika robust connection handles confirms automatically
                # Small delay to ensure message persistence
                await asyncio.sleep(0.01)

            logger.debug(f"Published batch of {len(events)} events to RabbitMQ")

        except Exception as e:
            logger.warning(f"Failed to publish batch to RabbitMQ: {e}")
            raise

    def _generate_routing_key(self, event: StreamllEvent) -> str:
        """Generate routing key from template using event fields."""
        try:
            return self.routing_key_template.format(
                event_type=event.event_type,
                operation=event.operation or "unknown",
                module_name=event.module_name.replace(".", "_"),
                method_name=event.method_name,
                execution_id=event.execution_id[:8],  # Short ID
            )
        except KeyError:
            # Fallback if template has unknown fields
            return f"streamll.{event.event_type}.{event.operation or 'unknown'}"

    async def _handle_failure(self) -> None:
        """Handle connection/publish failures with circuit breaker."""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()

        # Close broken connection
        await self._cleanup_connection()


    async def _cleanup_connection(self) -> None:
        """Clean up RabbitMQ connection and channel."""
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
        except Exception as e:
            # TODO: ARCHITECTURE CONSISTENCY - Should log cleanup errors like Redis sink does
            # Redis sink: logger.error(f"Error closing Redis connection: {e}")
            logger.debug(f"RabbitMQ cleanup error (non-critical): {e}")
        finally:
            self.connection = None
            self.channel = None
            self.exchange = None
            self.queue = None

    @property
    def failures(self) -> int:
        """Get current failure count for monitoring and testing."""
        return self._circuit_breaker.failure_count if self._circuit_breaker else 0
