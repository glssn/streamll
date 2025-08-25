"""Base consumer interface for StreamLL event processing."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from streamll.models import StreamllEvent

T = TypeVar("T", bound=StreamllEvent)
EventHandler = Callable[[StreamllEvent], None]
AsyncEventHandler = Callable[[StreamllEvent], asyncio.Future]


@dataclass
class ConsumerConfig:
    """Configuration for consumers."""

    validate_events: bool = True
    on_validation_error: str = "log"  # "log", "raise", "ignore"
    batch_size: int = 1
    batch_timeout: float = 1.0
    enable_checkpointing: bool = False
    consumer_group: str | None = None


class BaseConsumer(ABC):
    """Abstract base class for event consumers.

    Provides common functionality for all consumer implementations.
    """

    def __init__(self, config: ConsumerConfig | None = None):
        """Initialize consumer with configuration.

        Args:
            config: Consumer configuration
        """
        self.config = config or ConsumerConfig()
        self._handlers: dict[str, list[EventHandler]] = {}
        self._type_handlers: dict[type[StreamllEvent], list[EventHandler]] = {}
        self._running = False

    def register_handler(
        self, event_type: str | type[StreamllEvent], handler: EventHandler
    ) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type string or event class
            handler: Function to handle the event

        Example:
            consumer.register_handler("optimization.trial", handle_trial)
            consumer.register_handler(OptimizationTrialEvent, handle_trial)
        """
        if isinstance(event_type, str):
            # String-based registration
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
        else:
            # Type-based registration
            if event_type not in self._type_handlers:
                self._type_handlers[event_type] = []
            self._type_handlers[event_type].append(handler)

    def on(self, event_type: str | type[StreamllEvent]):
        """Decorator for registering handlers.

        Args:
            event_type: Event type to handle

        Example:
            @consumer.on("optimization.trial")
            def handle_trial(event: OptimizationTrialEvent):
                print(f"Trial {event.trial_number}: {event.score}")
        """

        def decorator(func: EventHandler) -> EventHandler:
            self.register_handler(event_type, func)
            return func

        return decorator

    def _dispatch_event(self, event: StreamllEvent) -> None:
        """Dispatch an event to registered handlers.

        Args:
            event: Event to dispatch
        """
        # Dispatch to string-based handlers
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._handle_error(e, event)

        # Dispatch to type-based handlers
        for event_class, class_handlers in self._type_handlers.items():
            if isinstance(event, event_class):
                for handler in class_handlers:
                    try:
                        handler(event)
                    except Exception as e:
                        self._handle_error(e, event)

    def _handle_error(self, error: Exception, event: StreamllEvent) -> None:
        """Handle errors during event processing.

        Args:
            error: The exception that occurred
            event: The event that caused the error
        """
        if self.config.on_validation_error == "raise":
            raise error
        elif self.config.on_validation_error == "log":
            pass
        # "ignore" - do nothing

    @abstractmethod
    async def start(self) -> None:
        """Start consuming events."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop consuming events."""
        pass

    @abstractmethod
    async def consume_one(self) -> StreamllEvent | None:
        """Consume a single event.

        Returns:
            The next event or None if no events available
        """
        pass

    async def consume_forever(self) -> None:
        """Consume events continuously until stopped."""
        self._running = True
        while self._running:
            try:
                event = await self.consume_one()
                if event:
                    self._dispatch_event(event)
                else:
                    # No event, sleep briefly
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                await asyncio.sleep(1.0)  # Back off on errors

    def run(self) -> None:
        """Synchronous entry point for running the consumer."""
        asyncio.run(self.run_async())

    async def run_async(self) -> None:
        """Async entry point for running the consumer."""
        try:
            await self.start()
            await self.consume_forever()
        finally:
            await self.stop()

    async def __aenter__(self) -> BaseConsumer:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
