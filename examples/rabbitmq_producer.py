#!/usr/bin/env python
"""Example RabbitMQ producer using StreamLL.

This example demonstrates:
1. Setting up a RabbitMQ sink
2. Using the @streamll.instrument decorator
3. Using the streamll.trace context manager
4. Sending custom events
"""

import logging
import time

import streamll
from streamll.sinks.rabbitmq import RabbitMQSink

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the producer example."""
    # Create RabbitMQ sink
    sink = RabbitMQSink(
        url="amqp://guest:guest@localhost:5672/",
        exchange="streamll",
        routing_key="events",
        buffer_size=100,
        batch_size=10,
    )
    
    # Start the sink
    sink.start()
    logger.info("RabbitMQ sink started")
    
    # Configure StreamLL with the sink
    with streamll.configure(sinks=[sink]):
        # Example 1: Using trace context manager
        logger.info("Sending trace events...")
        with streamll.trace("data_processing") as ctx:
            # Simulate some work
            time.sleep(0.1)
            
            # Send custom events
            ctx.emit("progress", data={"step": 1, "total": 3})
            time.sleep(0.1)
            
            ctx.emit("progress", data={"step": 2, "total": 3})
            time.sleep(0.1)
            
            ctx.emit("progress", data={"step": 3, "total": 3})
            
        # Example 2: Multiple operations
        logger.info("Sending multiple operation events...")
        for i in range(5):
            with streamll.trace(f"operation_{i}") as ctx:
                # Simulate varying work
                work_time = 0.05 * (i + 1)
                time.sleep(work_time)
                
                # Send metrics
                ctx.emit("metrics", data={
                    "operation_id": i,
                    "processing_time": work_time,
                    "items_processed": (i + 1) * 10,
                })
        
        # Example 3: Error handling
        logger.info("Sending error event...")
        try:
            with streamll.trace("risky_operation") as ctx:
                ctx.emit("attempting", data={"risk_level": "high"})
                # Simulate an error
                raise ValueError("Something went wrong!")
        except ValueError:
            pass  # Error is automatically captured by trace context
        
        # Example 4: Batch of custom events
        logger.info("Sending batch of custom events...")
        with streamll.trace("batch_operation") as ctx:
            for i in range(10):
                ctx.emit("item_processed", data={
                    "item_id": f"item_{i}",
                    "status": "success" if i % 3 != 0 else "warning",
                    "value": i * 100,
                })
    
    # Flush remaining events
    sink.flush()
    logger.info("Flushed remaining events")
    
    # Stop the sink
    sink.stop()
    logger.info("RabbitMQ sink stopped")
    
    logger.info("\nProducer finished! Check the consumer to see the events.")


if __name__ == "__main__":
    main()