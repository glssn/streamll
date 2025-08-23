"""Circuit breaker pattern implementation for fault tolerance."""

import logging
import time

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern to prevent thundering herd and cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail immediately
    - HALF_OPEN: Recovery timeout elapsed, next request tests if service recovered

    This implementation is shared between Redis and RabbitMQ sinks for consistency.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.is_open = False

    def record_success(self) -> None:
        """Record successful operation and reset circuit."""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None

    def record_failure(self) -> None:
        """Record failed operation and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def should_attempt(self) -> bool:
        """Check if we should attempt operation."""
        if not self.is_open:
            return True

        # Check if recovery timeout has elapsed (move to half-open state)
        if self.last_failure_time and (
            time.time() - self.last_failure_time > self.recovery_timeout
        ):
            logger.info("Circuit breaker attempting recovery (half-open state)")
            return True

        return False

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None
        logger.info("Circuit breaker manually reset")

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        if not self.is_open:
            return "CLOSED"
        elif self.last_failure_time and (
            time.time() - self.last_failure_time > self.recovery_timeout
        ):
            return "HALF_OPEN"
        else:
            return "OPEN"
