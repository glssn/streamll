"""Unit tests for @streamll.instrument decorator."""

import dspy
import pytest

import streamll
from tests.fixtures.mock_dspy import setup_mock_dspy
from tests.test_helpers import EventCapturingSink


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
            result = module(x=5)

        sink.stop()

        assert len(sink.events) > 0
        assert result["result"] == 10

    def test_decorator_preserves_module_behavior(self):
        """Test @instrument doesn't break module functionality."""
        setup_mock_dspy()

        class PlainModule(dspy.Module):
            def forward(self, x, y):
                return x + y

        @streamll.instrument
        class DecoratedModule(dspy.Module):
            def forward(self, x, y):
                return x + y

        plain = PlainModule()
        decorated = DecoratedModule()

        assert plain(3, 4) == decorated(3, 4)

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

        assert len(sink.events) > 0
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

    def test_decorator_can_be_applied_to_dspy_predict(self):
        """Test @instrument can be applied to dspy.Predict subclass (decorator acceptance)."""
        setup_mock_dspy()

        @streamll.instrument
        class InstrumentedPredict(dspy.Predict):
            pass

        assert hasattr(InstrumentedPredict, "_streamll_instrumented")
        assert InstrumentedPredict._streamll_instrumented is True

        predict = InstrumentedPredict("question -> answer")
        assert predict is not None
        assert hasattr(predict, "callbacks")
