"""FastStream broker factory for streamll.

Provides lazy import of FastStream brokers to avoid requiring all dependencies.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StreamllBroker(Protocol):
    """Minimal broker interface for streamll.

    We only need publish() for sinks, and subscriber() for consumers.
    """

    async def start(self) -> None:
        """Start the broker connection."""
        ...

    async def close(self) -> None:
        """Close the broker connection."""
        ...

    async def stop(self) -> None:
        """Stop the broker connection."""
        ...

    async def publish(
        self,
        message: dict,
        /,
        channel: str | None = None,
        list: str | None = None,
        stream: str | None = None,
        queue: str | None = None,
        exchange: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Publish a message to the broker."""
        ...

    def subscriber(
        self,
        channel: str | None = None,
        list: str | None = None,
        stream: str | None = None,
        queue: str | None = None,
        exchange: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a subscriber for messages."""
        ...


def create_broker(url: str, **kwargs) -> StreamllBroker:
    """Create a FastStream broker from URL.

    Args:
        url: Broker URL (redis://, amqp://, nats://, kafka://)
        **kwargs: Additional broker-specific configuration

    Returns:
        FastStream broker instance

    Raises:
        ImportError: If broker dependencies not installed
        ValueError: If URL scheme not supported
    """
    # Parse URL scheme
    scheme = url.split("://")[0].lower()

    if scheme == "redis":
        try:
            from faststream.redis import RedisBroker
            # Temporarily use default JSON format to debug communication
            return RedisBroker(url, **kwargs)
        except ImportError:
            raise ImportError(
                "Redis support not installed. "
                "Install with: pip install 'streamll[redis]' or 'faststream[redis]'"
            )

    elif scheme in ("amqp", "rabbitmq"):
        try:
            from faststream.rabbit import RabbitBroker

            return RabbitBroker(url, **kwargs)
        except ImportError:
            raise ImportError(
                "RabbitMQ support not installed. "
                "Install with: pip install 'streamll[rabbitmq]' or 'faststream[rabbit]'"
            )

    elif scheme == "nats":
        try:
            from faststream.nats import NatsBroker

            return NatsBroker(url, **kwargs)
        except ImportError:
            raise ImportError(
                "NATS support not installed. "
                "Install with: pip install 'streamll[nats]' or 'faststream[nats]'"
            )

    elif scheme == "kafka":
        try:
            from faststream.kafka import KafkaBroker

            return KafkaBroker(url, **kwargs)
        except ImportError:
            raise ImportError(
                "Kafka support not installed. "
                "Install with: pip install 'streamll[kafka]' or 'faststream[kafka]'"
            )

    else:
        raise ValueError(
            f"Unsupported broker URL scheme: {scheme}. "
            f"Supported: redis://, amqp://, rabbitmq://, nats://, kafka://"
        )
