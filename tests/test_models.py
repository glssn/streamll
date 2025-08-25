"""Data contract tests for EPIC-001: Core Event Model and Semantic Conventions."""

import json
from datetime import UTC

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from streamll.models import StreamllEvent


@pytest.mark.unit
class TestStreamllEventDataContract:
    """Test the StreamllEvent data contract and schema."""

    def test_event_creation_with_minimal_fields(self):
        """Events should be creatable with just required fields."""
        event = StreamllEvent(
            execution_id="exec123",
            event_type="start",
        )

        # Auto-generated fields
        assert len(event.event_id) == 12  # nanoid default size
        assert event.timestamp.tzinfo == UTC
        assert event.execution_id == "exec123"

        # Default values
        assert event.module_name == "unknown"
        assert event.method_name == "forward"
        assert event.operation is None
        assert event.data == {}
        assert event.tags == {}

    def test_event_with_all_fields(self):
        """Events should accept all optional fields."""
        event = StreamllEvent(
            execution_id="exec456",
            event_type="operation_start",
            operation="retrieval",
            module_name="RAGModule",
            method_name="retrieve_documents",
            data={"query": "What is Python?", "k": 5, "source": "vector_db"},
            tags={"environment": "production", "user_id": "user123"},
        )

        assert event.execution_id == "exec456"
        assert event.event_type == "operation_start"
        assert event.operation == "retrieval"
        assert event.module_name == "RAGModule"
        assert event.method_name == "retrieve_documents"
        assert event.data["query"] == "What is Python?"
        assert event.tags["environment"] == "production"

    def test_event_serialization_to_json(self):
        """Events should serialize to JSON for transport."""
        event = StreamllEvent(
            execution_id="exec789",
            event_type="token",
            data={"content": "Hello", "field": "answer", "is_final": False},
        )

        # Should serialize without errors
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)

        # Check key fields present
        assert parsed["execution_id"] == "exec789"
        assert parsed["event_type"] == "token"
        assert parsed["data"]["content"] == "Hello"

        # Timestamp should be ISO format
        assert "T" in parsed["timestamp"]
        assert parsed["timestamp"].endswith("Z")

    def test_event_deserialization_from_json(self):
        """Events should deserialize from JSON."""
        json_data = {
            "event_id": "test123",
            "execution_id": "exec999",
            "timestamp": "2024-01-01T12:00:00Z",
            "event_type": "end",
            "operation": "chain_of_thought",
            "data": {"success": True},
        }

        event = StreamllEvent(**json_data)
        assert event.event_id == "test123"
        assert event.execution_id == "exec999"
        assert event.event_type == "end"
        assert event.operation == "chain_of_thought"
        assert event.data["success"] is True

    @pytest.mark.parametrize(
        "event_type",
        ["start", "end", "token", "error"],
    )
    def test_common_event_types(self, event_type):
        """Common event types should be accepted."""
        event = StreamllEvent(
            execution_id="exec_test",
            event_type=event_type,
        )
        assert event.event_type == event_type

    @pytest.mark.parametrize(
        "operation",
        ["retrieval", "ocr_extraction", "chain_of_thought", "llm_prediction", "custom_operation"],
    )
    def test_flexible_operation_types(self, operation):
        """Operation field should accept any string value."""
        event = StreamllEvent(
            execution_id="exec_test",
            event_type="start",
            operation=operation,
        )
        assert event.operation == operation

    def test_required_fields_validation(self):
        """Missing required fields should raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            StreamllEvent()  # Missing execution_id and event_type

        errors = exc_info.value.errors()
        required_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}
        assert "execution_id" in required_fields
        assert "event_type" in required_fields

    @given(
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.one_of(
                st.text(),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
        )
    )
    def test_data_field_accepts_json_serializable_dict(self, data):
        """Event data field should accept any JSON-serializable dict."""
        event = StreamllEvent(execution_id="exec_test", event_type="test", data=data)

        # Should serialize without error
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["data"] == data

    def test_tags_field_string_values_only(self):
        """Tags should only accept string values."""
        # Valid tags
        event = StreamllEvent(
            execution_id="exec_test", event_type="test", tags={"env": "prod", "user": "123"}
        )
        assert event.tags == {"env": "prod", "user": "123"}

        # Invalid tags should fail validation
        with pytest.raises(ValidationError):
            StreamllEvent(
                execution_id="exec_test",
                event_type="test",
                tags={"count": 123},  # Non-string value
            )


@pytest.mark.unit
class TestDSPySemanticConventions:
    """Test DSPy-specific event patterns and conventions."""

    def test_dspy_module_lifecycle_events(self):
        """DSPy module start/end events should follow conventions."""
        start_event = StreamllEvent(
            execution_id="dspy_exec",
            event_type="start",
            operation="module_forward",
            module_name="RAGModule",
            data={
                "signature": "context, question -> answer",
                "input_args": {"question": "What is DSPy?"},
            },
        )

        end_event = StreamllEvent(
            execution_id="dspy_exec",
            event_type="end",
            operation="module_forward",
            module_name="RAGModule",
            data={
                "signature": "context, question -> answer",
                "output": {"answer": "DSPy is a framework..."},
                "duration_ms": 1250.5,
            },
        )

        # Events should share execution context
        assert start_event.execution_id == end_event.execution_id
        assert start_event.module_name == end_event.module_name
        assert start_event.operation == end_event.operation

    def test_token_streaming_events(self):
        """Token events should capture streaming LLM output."""
        token_event = StreamllEvent(
            execution_id="llm_stream",
            event_type="token",
            module_name="ChainOfThought",
            data={
                "content": "The answer is",
                "field": "reasoning",
                "position": 42,
                "is_final": False,
            },
        )

        assert token_event.event_type == "token"
        assert token_event.data["content"] == "The answer is"
        assert token_event.data["is_final"] is False

    def test_retrieval_operation_events(self):
        """Retrieval operations should capture query and results."""
        retrieval_event = StreamllEvent(
            execution_id="rag_exec",
            event_type="operation_end",
            operation="retrieval",
            module_name="VectorRetriever",
            data={
                "query": "Python programming",
                "k": 5,
                "retrieved_count": 3,
                "scores": [0.95, 0.87, 0.82],
                "source": "knowledge_base",
            },
        )

        assert retrieval_event.operation == "retrieval"
        assert retrieval_event.data["retrieved_count"] == 3
        assert len(retrieval_event.data["scores"]) == 3

    def test_custom_user_operations(self):
        """Users should be able to define custom operations."""
        ocr_event = StreamllEvent(
            execution_id="document_proc",
            event_type="start",
            operation="ocr_extraction",
            module_name="DocumentProcessor",
            data={"image_path": "/path/to/scan.pdf", "pages": [1, 2, 3], "engine": "tesseract"},
            tags={"document_type": "invoice", "priority": "high"},
        )

        assert ocr_event.operation == "ocr_extraction"
        assert ocr_event.tags["document_type"] == "invoice"
        assert "/path/to/scan.pdf" in ocr_event.data["image_path"]

    def test_error_event_structure(self):
        """Error events should capture exception details."""
        error_event = StreamllEvent(
            execution_id="failed_exec",
            event_type="error",
            operation="llm_prediction",
            module_name="Predictor",
            data={
                "error_type": "ValidationError",
                "message": "Invalid signature format",
                "traceback": "File '/path/to/file.py'...",
                "recovery_attempted": False,
            },
        )

        assert error_event.event_type == "error"
        assert error_event.data["error_type"] == "ValidationError"

    def test_event_ordering_by_timestamp(self):
        """Events should be orderable by timestamp."""
        # Create events with slight time differences
        events = []
        for i in range(3):
            event = StreamllEvent(
                execution_id="ordered_test", event_type="test", data={"sequence": i}
            )
            events.append(event)

        # Sort by timestamp
        sorted_events = sorted(events, key=lambda e: e.timestamp)

        # Should maintain creation order (assuming rapid creation)
        for i, event in enumerate(sorted_events):
            assert event.data["sequence"] == i
