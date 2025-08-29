"""RabbitMQ consumer for StreamLL events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from streamll.consumer.base import BaseConsumer, ConsumerConfig
from streamll.models import StreamllEvent

logger = logging.getLogger(__name__)


class RabbitMQConsumer(BaseConsumer):
    """Consumer for reading StreamLL events from RabbitMQ.
    
    Provides high-level interface for consuming events with:
    - Type-safe event handlers
    - Automatic deserialization
    - Queue management
    - Message acknowledgment
    - Batch processing
    """
    
    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost:5672/",
        exchange: str = "streamll",
        queue: str = "streamll_events",
        routing_keys: list[str] | None = None,
        auto_ack: bool = False,
        prefetch_count: int = 10,
        config: ConsumerConfig | None = None,
    ):
        """Initialize RabbitMQ consumer.
        
        Args:
            url: RabbitMQ connection URL
            exchange: Exchange to bind to
            queue: Queue name to consume from
            routing_keys: Routing keys to bind (default: ["events"])
            auto_ack: Auto-acknowledge messages
            prefetch_count: Number of unacked messages to prefetch
            config: Additional consumer configuration
        """
        super().__init__(config)
        
        self.url = url
        self.exchange = exchange
        self.queue = queue
        self.routing_keys = routing_keys or ["events"]
        self.auto_ack = auto_ack
        self.prefetch_count = prefetch_count
        
        self._connection = None
        self._channel = None
        self._queue_obj = None
        self._consumer_tag = None
        
    async def start(self) -> None:
        """Start the consumer and set up RabbitMQ connection."""
        try:
            import aio_pika
        except ImportError:
            raise ImportError(
                "aio-pika not installed. "
                "Install with: pip install streamll[rabbitmq-consumer]"
            ) from None
            
        # Connect to RabbitMQ
        try:
            self._connection = await aio_pika.connect_robust(self.url)
            self._channel = await self._connection.channel()
            
            # Set QoS
            await self._channel.set_qos(prefetch_count=self.prefetch_count)
            
            # Declare exchange
            exchange_obj = await self._channel.declare_exchange(
                self.exchange,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            
            # Declare queue
            self._queue_obj = await self._channel.declare_queue(
                self.queue,
                durable=True,
            )
            
            # Bind queue to exchange with routing keys
            for routing_key in self.routing_keys:
                await self._queue_obj.bind(exchange_obj, routing_key=routing_key)
                
            logger.info(
                f"Connected to RabbitMQ - Queue: {self.queue}, "
                f"Exchange: {self.exchange}, Keys: {self.routing_keys}"
            )
            
            self._running = True
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to RabbitMQ: {e}") from e
            
    async def stop(self) -> None:
        """Stop the consumer and close connections."""
        self._running = False
        
        if self._consumer_tag:
            try:
                await self._queue_obj.cancel(self._consumer_tag)
            except Exception:
                pass
                
        if self._channel:
            try:
                await self._channel.close()
            except Exception:
                pass
                
        if self._connection:
            try:
                await self._connection.close()
            except Exception:
                pass
                
        logger.info("Closed RabbitMQ connection")
        
    async def consume_one(self) -> StreamllEvent | None:
        """Consume a single event from RabbitMQ.
        
        Returns:
            Next event or None if no events available
        """
        if not self._running or not self._queue_obj:
            return None
            
        try:
            import aio_pika
            
            # Get single message with timeout
            message = await asyncio.wait_for(
                self._queue_obj.get(no_ack=self.auto_ack),
                timeout=1.0
            )
            
            if message:
                try:
                    # Parse message body
                    event_dict = json.loads(message.body.decode())
                    
                    # Create typed event
                    event = StreamllEvent(**event_dict)
                    
                    # Acknowledge if not auto-ack
                    if not self.auto_ack:
                        await message.ack()
                        
                    return event
                    
                except Exception as e:
                    # Handle deserialization errors
                    if not self.auto_ack:
                        await message.nack(requeue=False)  # Don't requeue bad messages
                        
                    if self.config.on_validation_error == "raise":
                        raise
                    elif self.config.on_validation_error == "log":
                        logger.error(f"Failed to deserialize message: {e}")
                        
        except asyncio.TimeoutError:
            return None
        except aio_pika.exceptions.QueueEmpty:
            return None
        except Exception as e:
            if self._running:
                logger.error(f"Error consuming message: {e}")
            return None
            
    async def consume_batch(self, max_events: int | None = None) -> list[StreamllEvent]:
        """Consume a batch of events from RabbitMQ.
        
        Args:
            max_events: Maximum events to consume (default: batch_size)
            
        Returns:
            List of events
        """
        if not self._running:
            return []
            
        max_events = max_events or self.config.batch_size
        events = []
        
        for _ in range(max_events):
            event = await self.consume_one()
            if event:
                events.append(event)
            else:
                break  # No more messages available
                
        return events
        
    async def consume_forever(self) -> None:
        """Consume events continuously using async iterator."""
        if not self._queue_obj:
            raise RuntimeError("Consumer not started")
            
        async with self._queue_obj.iterator() as queue_iter:
            self._consumer_tag = queue_iter.consumer_tag
            
            async for message in queue_iter:
                if not self._running:
                    break
                    
                try:
                    # Parse message
                    event_dict = json.loads(message.body.decode())
                    event = StreamllEvent(**event_dict)
                    
                    # Dispatch to handlers
                    self._dispatch_event(event)
                    
                    # Acknowledge
                    if not self.auto_ack:
                        await message.ack()
                        
                except Exception as e:
                    if not self.auto_ack:
                        await message.nack(requeue=False)
                        
                    if self.config.on_validation_error == "raise":
                        raise
                    elif self.config.on_validation_error == "log":
                        logger.error(f"Error processing message: {e}")
                        
    def consume_sync(self) -> StreamllEvent:
        """Synchronous consume for simpler use cases.
        
        Returns:
            Next event (blocks until available)
        """
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.start())
            
            while True:
                event = loop.run_until_complete(self.consume_one())
                if event:
                    return event
                # Small sleep to prevent busy loop
                loop.run_until_complete(asyncio.sleep(0.01))
        finally:
            loop.run_until_complete(self.stop())
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
                event = loop.run_until_complete(self.consume_one())
                if event:
                    yield event
                    count += 1
                else:
                    # No events, small sleep
                    loop.run_until_complete(asyncio.sleep(0.1))
                    
        finally:
            loop.run_until_complete(self.stop())
            loop.close()