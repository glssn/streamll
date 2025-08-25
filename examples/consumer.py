#!/usr/bin/env python
"""Example of consuming StreamLL events without DSPy dependencies.

This demonstrates how lightweight consumers like OptiViz can process
StreamLL events without pulling in heavyweight dependencies.
"""

import asyncio

from streamll import StreamllEvent
from streamll.consumer.redis import RedisStreamConsumer


# Example 1: Simple synchronous consumption
def simple_consumer_example():
    """Simplest way to consume events."""

    consumer = RedisStreamConsumer(redis_url="redis://localhost:6379", stream_key="streamll_events")

    # Register handlers for specific event types
    @consumer.on("optimization.trial")
    def handle_trial(event: StreamllEvent):
        pass

    @consumer.on("token")
    def handle_token(event: StreamllEvent):
        pass

    # Run forever (Ctrl+C to stop)
    consumer.run()


# Example 2: Async consumption with type-safe handlers
async def async_consumer_example():
    """Async consumption for better performance."""

    consumer = RedisStreamConsumer(
        redis_url="redis://localhost:6379",
        stream_key="streamll_events",
        batch_size=100,  # Process in batches
    )

    # Track metrics
    trial_scores = []
    token_count = 0

    @consumer.on("optimization.trial")  # Use event type string
    def handle_trial(event: StreamllEvent):
        score = event.data.get("score", 0)
        trial_scores.append(score)
        sum(trial_scores) / len(trial_scores)

    @consumer.on("token")
    def handle_token(event: StreamllEvent):
        nonlocal token_count
        token_count += 1
        if token_count % 100 == 0:
            pass

    @consumer.on("error")
    def handle_error(event: StreamllEvent):
        pass

    # Run with async context manager
    async with consumer:
        await consumer.consume_forever()


# Example 3: Consumer groups for distributed processing
def consumer_group_example():
    """Use consumer groups for distributed processing."""

    # Multiple consumers can share work via consumer groups
    consumer = RedisStreamConsumer(
        redis_url="redis://localhost:6379",
        stream_key="streamll_events",
        consumer_group="optimization-processors",  # Group name
        consumer_name="worker-1",  # Unique within group
    )

    @consumer.on("optimization.trial")
    def process_trial(event: OptimizationTrialEvent):
        # Simulate heavy processing
        import time

        time.sleep(0.1)

        # Save to database, update dashboard, etc.

    consumer.run()


# Example 4: Iterator interface for batch processing
def batch_processing_example():
    """Process events in batches using iterator."""

    consumer = RedisStreamConsumer(
        redis_url="redis://localhost:6379",
        stream_key="streamll_events",
        start_id="0",  # Read from beginning
    )

    # Process first 1000 events
    for event in consumer.iter_events(max_events=1000):
        if isinstance(event, OptimizationTrialEvent):
            # Collect trials for analysis
            pass
        elif isinstance(event, TokenEvent):
            # Skip tokens for this analysis
            pass


# Example 5: Building OptiViz-style dashboard consumer
class OptiVizConsumer:
    """Example of a sophisticated consumer for optimization visualization."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.consumer = RedisStreamConsumer(
            redis_url=redis_url,
            stream_key="streamll:optimization",
            consumer_group="optiviz",
        )

        # State for visualization
        self.trials = []
        self.best_score = 0.0
        self.token_usage = {"prompt": 0, "completion": 0}

        # Register handlers
        self.consumer.on("optimization.trial")(self.handle_trial)
        self.consumer.on("optimization.complete")(self.handle_complete)

    def handle_trial(self, event: OptimizationTrialEvent):
        """Process trial for visualization."""
        self.trials.append(
            {
                "number": event.trial_number,
                "score": event.score,
                "parameters": event.parameters,
                "timestamp": event.timestamp,
            }
        )

        if event.score > self.best_score:
            self.best_score = event.score
            self.send_to_dashboard(
                {
                    "type": "new_best",
                    "trial": event.trial_number,
                    "score": event.score,
                }
            )

        # Update token usage
        if event.token_usage:
            for key, value in event.token_usage.items():
                self.token_usage[key] = self.token_usage.get(key, 0) + value

    def handle_complete(self, event):
        """Handle optimization completion."""
        self.send_to_dashboard(
            {
                "type": "complete",
                "total_trials": len(self.trials),
                "best_score": self.best_score,
                "token_usage": self.token_usage,
            }
        )

    def send_to_dashboard(self, data):
        """Send update to web dashboard via WebSocket."""
        # This would send to your real dashboard

    def run(self):
        """Start consuming events."""
        self.consumer.run()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "simple":
            simple_consumer_example()
        elif example == "async":
            asyncio.run(async_consumer_example())
        elif example == "group":
            consumer_group_example()
        elif example == "batch":
            batch_processing_example()
        elif example == "optiviz":
            viz = OptiVizConsumer()
            viz.run()
        else:
            pass
    else:
        pass
