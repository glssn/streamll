"""Base sink interface for streamll.

All sinks must implement this interface to receive events.
"""

from abc import ABC, abstractmethod

from streamll.models import StreamllEvent


class BaseSink(ABC):
    """Base class for event sinks."""

    def __init__(
        self,
        buffer_size: int = 1000,
        batch_size: int = 100,
        flush_interval: float = 0.1,
    ):
        """Initialize sink with buffering configuration.

        Args:
            buffer_size: Maximum events to buffer
            batch_size: Maximum events per batch write
            flush_interval: Seconds between flush attempts

        TODO: ARCHITECTURE CONSISTENCY - Not all sinks use these base parameters:
        - RabbitMQ sink ignores batch_size and flush_interval
        - Redis sink uses different parameter names (max_batch_size vs batch_size)
        - Buffer overflow strategies are inconsistent across sinks
        """
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.is_running = False

    @abstractmethod
    def start(self) -> None:
        """Start the sink (open connections, start threads, etc).

        Called once when sink is registered.
        """
        # Open connections
        # Start background tasks
        # Set is_running = True
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the sink gracefully.

        Should flush any buffered events and close connections.
        """
        # Set is_running = False
        # Flush remaining events
        # Close connections
        # Wait for background tasks
        pass

    @abstractmethod
    def handle_event(self, event: StreamllEvent) -> None:
        """Handle a single event.

        Args:
            event: The event to process

        This method should be fast and non-blocking.
        Events can be buffered for batch processing.
        """
        # Add to buffer
        # If buffer full, trigger flush
        # Or queue for background processing
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered events immediately.

        Called periodically and on shutdown.
        """
        # Write all buffered events
        # Clear buffer
        # Handle any errors
        pass

    def __enter__(self) -> "BaseSink":
        """Context manager entry - start the sink.

        Returns:
            Self for use in with statement
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stop the sink.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        self.stop()
