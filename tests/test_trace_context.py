"""Tests for execution context and ID resolution.

Tests the smart execution ID resolution and context management.
"""

from unittest.mock import patch

from streamll.context import _execution_context, get_execution_id


class TestExecutionIdResolution:
    """Test smart execution ID resolution priority."""

    def test_generates_new_id_when_no_context(self):
        """Should generate new nanoid when no context available."""

        # Clear any existing context
        _execution_context.set(None)

        # Should generate new IDs
        id1 = get_execution_id()
        id2 = get_execution_id()

        # IDs should be different and proper length
        assert id1 != id2
        assert len(id1) == 12  # nanoid default size
        assert len(id2) == 12
        assert isinstance(id1, str)
        assert isinstance(id2, str)

    @patch("dspy.utils.callback.ACTIVE_CALL_ID")
    def test_uses_dspy_context_when_available(self, mock_active_call_id):
        """Should use DSPy's ACTIVE_CALL_ID when available."""

        # Mock DSPy context variable
        mock_active_call_id.get.return_value = "dspy_call_123"

        # Should return DSPy's ID
        result = get_execution_id()
        assert result == "dspy_call_123"

        # Verify DSPy context was checked
        mock_active_call_id.get.assert_called_once()

    @patch("dspy.utils.callback.ACTIVE_CALL_ID")
    def test_uses_streamll_context_when_no_dspy(self, mock_active_call_id):
        """Should use streamll context when DSPy context unavailable."""

        # Set streamll context
        test_context = {"execution_id": "streamll_exec_456"}
        _execution_context.set(test_context)

        # Mock DSPy context not available
        mock_active_call_id.get.return_value = None

        result = get_execution_id()
        assert result == "streamll_exec_456"

    @patch("dspy.utils.callback.ACTIVE_CALL_ID")
    def test_context_priority_order(self, mock_active_call_id):
        """Test that DSPy context takes priority over streamll context."""

        # Set both contexts
        streamll_context = {"execution_id": "streamll_should_not_be_used"}
        _execution_context.set(streamll_context)

        # Mock DSPy context available
        mock_active_call_id.get.return_value = "dspy_takes_priority"

        result = get_execution_id()
        assert result == "dspy_takes_priority"
        assert result != "streamll_should_not_be_used"

    def test_handles_dspy_import_error(self):
        """Should gracefully handle DSPy not being available."""

        # Clear any streamll context first
        _execution_context.set(None)

        # Mock the entire import to fail
        def mock_import(name, *args, **kwargs):
            if name == "dspy.utils.callback":
                raise ImportError("DSPy not available")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should fall back to generating new ID
            result = get_execution_id()
            assert isinstance(result, str)
            assert len(result) == 12

    @patch("dspy.utils.callback.ACTIVE_CALL_ID")
    def test_handles_empty_streamll_context(self, mock_active_call_id):
        """Should handle streamll context with no execution_id."""

        # Set context without execution_id
        _execution_context.set({"other_data": "value"})

        # Mock no DSPy context
        mock_active_call_id.get.return_value = None

        result = get_execution_id()
        # Should generate new ID since streamll context has no execution_id
        assert isinstance(result, str)
        assert len(result) == 12


class TestContextManagement:
    """Test context variable management and thread safety."""

    def test_context_isolation_between_threads(self):
        """Context variables should be isolated between threads."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        results = {}

        def set_and_get_context(thread_id: str):
            # Set different context in each thread
            test_context = {"execution_id": f"thread_{thread_id}"}
            _execution_context.set(test_context)

            # Small delay to ensure threads are interleaved
            time.sleep(0.01)

            # Get context back
            ctx = _execution_context.get()
            results[thread_id] = ctx["execution_id"] if ctx else None

        # Run multiple threads
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                futures.append(executor.submit(set_and_get_context, str(i)))

            # Wait for all to complete
            for future in futures:
                future.result()

        # Verify each thread kept its own context
        for i in range(10):
            assert results[str(i)] == f"thread_{str(i)}"

    def test_context_inheritance_in_async_tasks(self):
        """Context should be inherited by async tasks."""
        import asyncio

        async def test_async_context():
            # Set context in main task
            test_context = {"execution_id": "async_main"}
            _execution_context.set(test_context)

            async def child_task():
                # Child task should inherit context
                ctx = _execution_context.get()
                return ctx["execution_id"] if ctx else None

            # Create child task
            result = await child_task()
            return result

        # Run async test
        result = asyncio.run(test_async_context())
        assert result == "async_main"
