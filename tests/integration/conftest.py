import time

import pytest

from streamll.models import StreamllEvent


@pytest.fixture
def sample_integration_event():
    return StreamllEvent(
        execution_id="integration-test-001",
        event_type="test",
        operation="integration_test",
        data={"test": True, "timestamp": time.time()},
        tags={"environment": "test"},
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring real infrastructure"
    )
