#!/usr/bin/env python
"""Example RabbitMQ consumer for StreamLL events.

This example demonstrates:
1. Setting up a RabbitMQ consumer
2. Registering event handlers
3. Processing events in real-time
"""

import asyncio
import logging
from datetime import datetime

from streamll.consumer.rabbitmq import RabbitMQConsumer
from streamll.models import StreamllEvent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Run the consumer example."""
    # Create consumer
    consumer = RabbitMQConsumer(
        url="amqp://guest:guest@localhost:5672/",
        exchange="streamll",
        queue="streamll_demo",
        routing_keys=["events", "*.events"],  # Subscribe to multiple routing keys
        auto_ack=False,  # Manual acknowledgment for reliability
        prefetch_count=10,
    )
    
    # Track statistics
    stats = {
        "total_events": 0,
        "event_types": {},
        "start_time": datetime.now(),
    }
    
    # Register handler for all events
    @consumer.on("*")  # Wildcard to handle all event types
    def handle_all_events(event: StreamllEvent):
        """Process all events."""
        stats["total_events"] += 1
        event_type = event.event_type
        stats["event_types"][event_type] = stats["event_types"].get(event_type, 0) + 1
        
        # Log event details
        logger.info(
            f"[{event.timestamp}] {event.event_type} - "
            f"Source: {event.source} - Data: {event.data}"
        )
    
    # Register specific handler for operation start events
    @consumer.on("operation.start")
    def handle_operation_start(event: StreamllEvent):
        """Handle operation start events."""
        operation_name = event.data.get("operation_name", "unknown")
        logger.info(f"🚀 Operation started: {operation_name}")
    
    # Register handler for operation end events
    @consumer.on("operation.end")
    def handle_operation_end(event: StreamllEvent):
        """Handle operation end events."""
        operation_name = event.data.get("operation_name", "unknown")
        duration = event.data.get("duration", 0)
        logger.info(f"✅ Operation completed: {operation_name} (took {duration:.2f}s)")
    
    # Register handler for errors
    @consumer.on("operation.error")
    def handle_error(event: StreamllEvent):
        """Handle error events."""
        error = event.data.get("error", "Unknown error")
        logger.error(f"❌ Error occurred: {error}")
    
    # Start consuming
    logger.info("Starting RabbitMQ consumer...")
    logger.info(f"Listening on exchange '{consumer.exchange}' with queue '{consumer.queue}'")
    logger.info("Press Ctrl+C to stop")
    
    try:
        await consumer.start()
        
        # Consume events forever
        while True:
            event = await consumer.consume_one()
            if event:
                consumer._dispatch_event(event)
            else:
                await asyncio.sleep(0.1)  # No events, wait briefly
                
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        # Print statistics
        runtime = (datetime.now() - stats["start_time"]).total_seconds()
        logger.info("\n" + "="*50)
        logger.info("Consumer Statistics:")
        logger.info(f"  Total events: {stats['total_events']}")
        logger.info(f"  Runtime: {runtime:.1f} seconds")
        logger.info(f"  Events/sec: {stats['total_events']/runtime:.2f}")
        logger.info("  Event types:")
        for event_type, count in sorted(stats["event_types"].items()):
            logger.info(f"    {event_type}: {count}")
        logger.info("="*50)
        
        await consumer.stop()


def run_sync():
    """Synchronous entry point using iter_events."""
    # Create consumer
    consumer = RabbitMQConsumer(
        url="amqp://guest:guest@localhost:5672/",
        exchange="streamll",
        queue="streamll_demo_sync",
        routing_keys=["events"],
    )
    
    logger.info("Starting synchronous RabbitMQ consumer...")
    logger.info("Processing first 10 events...")
    
    # Process events using iterator interface
    for i, event in enumerate(consumer.iter_events(max_events=10), 1):
        logger.info(
            f"Event {i}: [{event.timestamp}] {event.event_type} - {event.data}"
        )
    
    logger.info("Processed 10 events, stopping.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        # Run synchronous version
        run_sync()
    else:
        # Run async version
        asyncio.run(main())