"""Unit tests for @streamll.instrument decorator."""

import dspy
import pytest

import streamll
from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink
from tests.fixtures.mock_dspy import setup_mock_dspy


class EventCapturingSink(BaseSink):
    """Test sink that captures events."""

    def __init__(self):
        super().__init__()
        self.events = []
        self.is_running = False

    def handle_event(self, event: StreamllEvent) -> None:
        self.events.append(event)

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def flush(self) -> None:
        pass

    def _write_batch(self, batch):
        pass


class TestInstrumentDecorator:
    """Test the @streamll.instrument decorator."""

    def test_decorator_on_class(self):
        """Test @instrument can decorate a DSPy module class."""
        setup_mock_dspy()

        @streamll.instrument
        class InstrumentedModule(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.ChainOfThought("question -> answer")

            def forward(self, question):
                return self.predict(question=question)

        # Should be able to instantiate
        module = InstrumentedModule()
        assert module is not None
        assert hasattr(module, "forward")

    def test_decorator_captures_events(self):
        """Test @instrument captures module execution events."""
        setup_mock_dspy()
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):

            @streamll.instrument
            class TrackedModule(dspy.Module):
                def __init__(self):
                    super().__init__()

                def forward(self, x):
                    return {"result": x * 2}

            module = TrackedModule()
            # Call module properly via __call__ instead of .forward()
            result = module(x=5)

        sink.stop()

        # Should capture events
        assert len(sink.events) > 0
        assert result["result"] == 10

    def test_decorator_preserves_module_behavior(self):
        """Test @instrument doesn't break module functionality."""
        setup_mock_dspy()

        # Create undecorated version
        class PlainModule(dspy.Module):
            def forward(self, x, y):
                return x + y

        # Create decorated version
        @streamll.instrument
        class DecoratedModule(dspy.Module):
            def forward(self, x, y):
                return x + y

        plain = PlainModule()
        decorated = DecoratedModule()

        # Both should produce same result
        assert plain.forward(3, 4) == decorated.forward(3, 4)

    def test_decorator_with_exception(self):
        """Test @instrument handles exceptions properly."""
        setup_mock_dspy()
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):

            @streamll.instrument
            class FailingModule(dspy.Module):
                def forward(self, x):
                    raise ValueError("Test error")

            module = FailingModule()

            with pytest.raises(ValueError, match="Test error"):
                module(x=1)

        sink.stop()

        # Should still capture events before error
        assert len(sink.events) > 0
        # Check for error event
        error_events = [e for e in sink.events if e.event_type == "error"]
        assert len(error_events) > 0

    def test_decorator_with_nested_modules(self):
        """Test @instrument works with nested DSPy modules."""
        setup_mock_dspy()
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):

            class SubModule(dspy.Module):
                def forward(self, x):
                    return x * 2

            @streamll.instrument
            class ParentModule(dspy.Module):
                def __init__(self):
                    super().__init__()
                    self.sub = SubModule()

                def forward(self, x):
                    return self.sub(x=x) + 1

            module = ParentModule()
            result = module(x=5)

        sink.stop()

        assert result == 11
        assert len(sink.events) > 0

    def test_decorator_multiple_instances(self):
        """Test multiple instances of decorated modules work independently."""
        setup_mock_dspy()
        sink = EventCapturingSink()
        sink.start()

        with streamll.configure(sinks=[sink]):

            @streamll.instrument
            class CounterModule(dspy.Module):
                def __init__(self):
                    super().__init__()
                    self.count = 0

                def forward(self):
                    self.count += 1
                    return self.count

            module1 = CounterModule()
            module2 = CounterModule()

            assert module1() == 1
            assert module2() == 1
            assert module1() == 2

        sink.stop()

        # Each call should generate events
        assert len(sink.events) >= 3
