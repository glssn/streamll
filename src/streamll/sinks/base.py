"""Base sink interface with built-in buffering and circuit breaker."""

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from threading import Lock

from streamll.models import StreamllEvent

logger = logging.getLogger(__name__)


class BaseSink(ABC):
    """Base class for event sinks with buffering and circuit breaker."""

    def __init__(
        self,
        buffer_size: int = 1000,
        batch_size: int = 100,
        flush_interval: float = 0.1,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
    ):
        """Initialize sink with buffering and circuit breaker.

        Args:
            buffer_size: Maximum events to buffer locally
            batch_size: Maximum events per batch write
            flush_interval: Seconds between automatic flush attempts
            failure_threshold: Failures before circuit opens
            recovery_timeout: Seconds before recovery attempt
        """
        # Buffering
        self.buffer_size = buffer_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer = deque(maxlen=buffer_size)
        self._buffer_lock = Lock()

        # Circuit breaker
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._last_failure_time = None
        self._circuit_open = False

        # State
        self.is_running = False

    @abstractmethod
    def start(self) -> None:
        """Start the sink (open connections, start threads, etc)."""
        self.is_running = True

    @abstractmethod
    def stop(self) -> None:
        """Stop the sink gracefully."""
        self.is_running = False
        self.flush()

    def handle_event(self, event: StreamllEvent) -> None:
        """Handle event with automatic buffering.

        Args:
            event: The event to process
        """
        with self._buffer_lock:
            self._buffer.append(event)
            if len(self._buffer) >= self.batch_size:
                self.flush()

    def flush(self) -> None:
        """Flush buffered events with circuit breaker protection."""
        if not self._should_attempt():
            logger.warning("Circuit breaker open, skipping flush")
            return

        with self._buffer_lock:
            if not self._buffer:
                return

            events = list(self._buffer)
            self._buffer.clear()

        try:
            self._write_batch(events)
            self._record_success()
        except Exception as e:
            logger.error(f"Failed to flush events: {e}")
            self._record_failure()
            # Re-buffer events on failure
            with self._buffer_lock:
                self._buffer.extend(events)

    def _write_batch(self, events: list[StreamllEvent]) -> None:
        """Write a batch of events to the sink.
        
        Default implementation writes events immediately one by one.
        Override this method for batch writing (e.g., Redis pipeline).

        Args:
            events: Events to write

        Raises:
            Exception: If write fails
        """
        # Default: write events one by one
        for event in events:
            self.handle_event(event)

    def _should_attempt(self) -> bool:
        """Check if we should attempt operation."""
        if not self._circuit_open:
            return True

        # Check recovery timeout
        if self._last_failure_time and (
            time.time() - self._last_failure_time > self.recovery_timeout
        ):
            logger.info("Circuit breaker attempting recovery")
            return True

        return False

    def _record_success(self) -> None:
        """Record successful operation."""
        self._failure_count = 0
        self._circuit_open = False
        self._last_failure_time = None

    def _record_failure(self) -> None:
        """Record failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._circuit_open = True
            logger.warning(f"Circuit breaker opened after {self._failure_count} failures")

    def __enter__(self) -> "BaseSink":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
