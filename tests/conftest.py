"""Shared test fixtures and configuration for streamll tests."""

import asyncio

import pytest

from streamll.models import StreamllEvent

# Import Redis fixtures
pytest_plugins = ["tests.fixtures.redis"]


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_event():
    """Sample StreamllEvent for testing."""
    return StreamllEvent(
        execution_id="test_exec_123",
        event_type="start",
        operation="test_operation",
        data={"key": "value"},
        tags={"test": "true"},
    )


@pytest.fixture
def sample_events():
    """List of sample StreamllEvents for testing."""
    return [
        StreamllEvent(
            execution_id="exec_1",
            event_type="start",
            operation="operation_1",
            data={"input": "test1"},
        ),
        StreamllEvent(
            execution_id="exec_1",
            event_type="end",
            operation="operation_1",
            data={"output": "result1"},
        ),
        StreamllEvent(
            execution_id="exec_2",
            event_type="error",
            operation="operation_2",
            data={"error": "Something went wrong"},
        ),
    ]


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "event_type": "token",
        "module_name": "TestModule",
        "data": {"token": "hello", "field": "answer"},
    }
