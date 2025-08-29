"""RabbitMQ consumer for StreamLL events."""

import asyncio
import json
import logging

from streamll.consumer.base import BaseConsumer, ConsumerConfig
from streamll.models import StreamllEvent

logger = logging.getLogger(__name__)


class RabbitMQConsumer(BaseConsumer):
    """Minimal RabbitMQ consumer for StreamLL events."""
    
    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost:5672/",
        exchange: str = "streamll",
        queue: str = "streamll_events",
        routing_keys: list[str] | None = None,
        prefetch_count: int = 10,
        config: ConsumerConfig | None = None,
    ):
        """Initialize RabbitMQ consumer."""
        super().__init__(config)
        self.url = url
        self.exchange = exchange
        self.queue = queue
        self.routing_keys = routing_keys or ["events"]
        self.prefetch_count = prefetch_count
        
        self._connection = None
        self._channel = None
        self._queue_obj = None
        
    async def start(self) -> None:
        """Connect to RabbitMQ and declare queue."""
        try:
            import aio_pika
        except ImportError:
            raise ImportError("Install with: pip install streamll[rabbitmq]") from None
            
        self._connection = await aio_pika.connect_robust(self.url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self.prefetch_count)
        
        # Declare exchange and queue
        exchange_obj = await self._channel.declare_exchange(
            self.exchange, aio_pika.ExchangeType.TOPIC, durable=True
        )
        self._queue_obj = await self._channel.declare_queue(self.queue, durable=True)
        
        # Bind routing keys
        for key in self.routing_keys:
            await self._queue_obj.bind(exchange_obj, routing_key=key)
            
        self._running = True
        logger.info(f"Connected to RabbitMQ: {self.queue} <- {self.routing_keys}")
        
    async def stop(self) -> None:
        """Close RabbitMQ connection."""
        self._running = False
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            
    async def consume_one(self) -> StreamllEvent | None:
        """Get next event from queue."""
        if not self._running or not self._queue_obj:
            return None
            
        try:
            import aio_pika
            message = await asyncio.wait_for(
                self._queue_obj.get(no_ack=False), timeout=1.0
            )
            
            if message:
                event_dict = json.loads(message.body.decode())
                event = StreamllEvent(**event_dict)
                await message.ack()
                return event
                
        except (asyncio.TimeoutError, aio_pika.exceptions.QueueEmpty):
            return None
        except Exception as e:
            logger.error(f"Error consuming: {e}")
            return None