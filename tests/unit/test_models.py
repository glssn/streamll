from datetime import UTC, datetime

from streamll.models import StreamllEvent, generate_event_id


class TestStreamllEvent:
    def test_event_creation(self):
        event = StreamllEvent(execution_id="test_exec", event_type="start", operation="test_op")

        assert event.execution_id == "test_exec"
        assert event.event_type == "start"
        assert event.operation == "test_op"
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)

    def test_event_defaults(self):
        event = StreamllEvent(execution_id="test", event_type="custom")

        assert event.module_name == "unknown"
        assert event.method_name == "forward"
        assert event.data == {}
        assert event.tags == {}

    def test_event_with_data(self):
        event = StreamllEvent(
            execution_id="test", event_type="custom", data={"key": "value", "count": 42}
        )

        assert event.data["key"] == "value"
        assert event.data["count"] == 42

    def test_event_with_tags(self):
        event = StreamllEvent(
            execution_id="test", event_type="custom", tags={"env": "test", "user": "alice"}
        )

        assert event.tags["env"] == "test"
        assert event.tags["user"] == "alice"

    def test_event_id_generation(self):
        id1 = generate_event_id()
        id2 = generate_event_id()

        assert id1 != id2
        assert len(id1) == 12
        assert len(id2) == 12

    def test_event_timestamp(self):
        event = StreamllEvent(execution_id="test", event_type="test")

        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == UTC
