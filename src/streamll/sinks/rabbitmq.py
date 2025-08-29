"""RabbitMQ sink for streaming events."""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink

logger = logging.getLogger(__name__)


class RabbitMQSink(BaseSink):
    """Writes events to RabbitMQ with async support."""

    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost:5672/",
        exchange: str = "streamll",
        routing_key: str = "events",
        buffer_size: int = 10000,
        batch_size: int = 100,
    ):
        """Initialize RabbitMQ sink.

        Args:
            url: RabbitMQ connection URL
            exchange: Exchange name
            routing_key: Routing key for messages
            buffer_size: Maximum events to buffer
            batch_size: Events per batch write
        """
        super().__init__(
            buffer_size=buffer_size,
            batch_size=batch_size,
            flush_interval=1.0,
            failure_threshold=3,
            recovery_timeout=30.0,
        )

        self.url = url
        self.exchange = exchange
        self.routing_key = routing_key

        # Async components
        self._loop = None
        self._executor = None
        self._connection = None
        self._channel = None

    def start(self) -> None:
        """Start the RabbitMQ sink."""
        super().start()

        # Create event loop and executor
        self._loop = asyncio.new_event_loop()
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Connect in background
        self._executor.submit(self._connect)

    def stop(self) -> None:
        """Stop the sink and close connections."""
        # Don't call super().stop() yet - we need executor for flush
        self.is_running = False
        self.flush()  # Flush before closing connections
        
        if self._executor and not self._executor._shutdown:
            # Close connection if we have one
            if self._connection:
                try:
                    self._executor.submit(self._disconnect).result(timeout=5)
                except Exception:
                    pass  # Connection might already be closed
            
            # Shutdown executor
            self._executor.shutdown(wait=True)
        
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    def _connect(self) -> None:
        """Connect to RabbitMQ."""
        try:
            import aio_pika
        except ImportError:
            logger.error(
                "aio-pika not installed. Install with: pip install streamll[rabbitmq-producer]"
            )
            self._record_failure()
            return

        asyncio.set_event_loop(self._loop)

        async def connect_async():
            try:
                self._connection = await aio_pika.connect_robust(self.url)
                self._channel = await self._connection.channel()

                # Declare exchange
                await self._channel.declare_exchange(
                    self.exchange,
                    aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                logger.info(f"Connected to RabbitMQ at {self.url}")
                self._record_success()
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                self._record_failure()

        self._loop.run_until_complete(connect_async())

    def _disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        if not self._connection:
            return

        async def disconnect_async():
            try:
                await self._connection.close()
                logger.info("Closed RabbitMQ connection")
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {e}")

        self._loop.run_until_complete(disconnect_async())

    def _write_batch(self, events: list[StreamllEvent]) -> None:
        """Write batch of events to RabbitMQ.

        Args:
            events: Events to write

        Raises:
            Exception: If write fails
        """
        if not self._channel:
            raise RuntimeError("RabbitMQ channel not initialized")

        async def publish_async():
            import aio_pika

            # Publish each event
            for event in events:
                # Serialize event
                event_dict = event.model_dump()
                if "timestamp" in event_dict:
                    event_dict["timestamp"] = event_dict["timestamp"].isoformat()

                message = aio_pika.Message(
                    body=json.dumps(event_dict).encode(),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                )

                # Publish to exchange
                exchange = await self._channel.get_exchange(self.exchange)
                await exchange.publish(message, routing_key=self.routing_key)

            logger.debug(f"Published {len(events)} events to RabbitMQ")

        # Run async publish in executor
        future = self._executor.submit(self._loop.run_until_complete, publish_async())
        future.result(timeout=10)  # Wait for completion

    def declare_queue(self, queue_name: str, routing_keys: list[str] | None = None) -> None:
        """Declare a queue and bind it to the exchange.

        Args:
            queue_name: Name of the queue
            routing_keys: List of routing keys to bind
        """
        if not self._channel:
            logger.error("Cannot declare queue: not connected")
            return

        async def declare_async():
            # Declare queue
            queue = await self._channel.declare_queue(queue_name, durable=True)

            # Bind to exchange
            exchange = await self._channel.get_exchange(self.exchange)
            for key in routing_keys or [self.routing_key]:
                await queue.bind(exchange, routing_key=key)

            logger.info(f"Declared queue {queue_name} with keys {routing_keys}")

        self._executor.submit(self._loop.run_until_complete, declare_async()).result(timeout=5)
