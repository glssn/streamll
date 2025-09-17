import asyncio
import os

import dspy
import pytest
from nanoid import generate

import streamll
from streamll.models import Event
from streamll.rabbitmq_consumer import RabbitMQEventConsumer
from streamll.redis_consumer import RedisEventConsumer
from streamll.sinks.rabbitmq import RabbitMQSink
from streamll.sinks.redis import RedisSink


def service_available(host: str = "localhost", port: int = 6379) -> bool:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


requires_redis = pytest.mark.skipif(
    not service_available("localhost", 6379),
    reason="Redis not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)

requires_rabbitmq = pytest.mark.skipif(
    not service_available("localhost", 5672),
    reason="RabbitMQ not available (run: docker-compose -f tests/docker-compose.yml up -d)",
)

requires_llm = pytest.mark.skipif(
    not (os.getenv("OPENROUTER_API_KEY") or service_available("localhost", 1234)),
    reason="No LLM available (set OPENROUTER_API_KEY or run local model)",
)


def get_llm_config():
    """Get LLM configuration - prefer local model, fallback to OpenRouter."""
    if service_available("localhost", 1234):
        return dspy.LM(
            model="openai/deepseek-r1-distill-qwen-7b",
            api_key="test",
            api_base="http://localhost:1234/v1",
            max_tokens=100,
            cache=False,
        )
    elif os.getenv("OPENROUTER_API_KEY"):
        return dspy.LM(
            model="openrouter/deepseek/deepseek-chat",
            max_tokens=100,
            cache=False,
        )
    else:
        pytest.skip("No LLM available")


# Configure dspy globally once for all tests
if service_available("localhost", 1234) or os.getenv("OPENROUTER_API_KEY"):
    lm = get_llm_config()
    dspy.settings.configure(lm=lm)


class TestFullPipeline:
    """Test complete pipeline: LLM -> Sink -> Consumer"""

    @requires_redis
    @requires_llm
    @pytest.mark.asyncio
    async def test_redis_full_pipeline_with_correlation(self):
        """Test complete Redis pipeline with user correlation."""
        # Unique identifiers for this test run
        stream_key = f"test_pipeline_{generate(size=8)}"
        user_id = f"user_{generate(size=6)}"

        # Set up consumer first
        consumer = RedisEventConsumer(broker_url="redis://localhost:6379", target=stream_key)

        received_events = []
        token_events = []

        @consumer.on("start")
        async def handle_start(event: Event):
            received_events.append(("start", event))
            assert event.data.get("user_id") == user_id

        @consumer.on("token")
        async def handle_token(event: Event):
            received_events.append(("token", event))
            token_events.append(event)
            assert event.data.get("user_id") == user_id
            assert event.execution_id is not None

        @consumer.on("end")
        async def handle_end(event: Event):
            received_events.append(("end", event))
            assert event.data.get("user_id") == user_id
            assert event.execution_id is not None

        # Start consumer
        consumer_task = asyncio.create_task(consumer.run())
        await asyncio.sleep(0.5)

        # Set up sink with correlation data
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        sink.start()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class CorrelatedQA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question, user_id=None):
                with streamll.trace("user_query", user_id=user_id):
                    return self.predict(question=question)

        # Run the instrumented module
        module = CorrelatedQA()
        module(question="Count from 1 to 3", user_id=user_id)

        sink.stop()

        # Wait for events to be consumed
        await asyncio.sleep(2.0)

        # Stop consumer
        await consumer.stop()
        consumer_task.cancel()

        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.CancelledError:
            pass

        # Verify we got all event types
        event_types = [event_type for event_type, _ in received_events]
        assert "start" in event_types, "Should receive start event"
        assert "end" in event_types, "Should receive end event"
        assert "token" in event_types, "Should receive token events"

        # Verify token streaming
        assert len(token_events) > 1, f"Should receive multiple tokens, got {len(token_events)}"

        # Verify correlation data
        for event_type, event in received_events:
            if event_type in ["start", "end"]:
                assert event.data.get("user_id") == user_id
            elif event_type == "token":
                assert event.data.get("user_id") == user_id
                assert "field" in event.data
                assert "token" in event.data
                assert "token_index" in event.data

        # Verify execution ID consistency - all events should have the same ID
        execution_ids = {event.execution_id for _, event in received_events}
        assert len(execution_ids) == 1, (
            f"All events should have same execution_id, got: {execution_ids}"
        )

    @requires_rabbitmq
    @requires_llm
    @pytest.mark.asyncio
    async def test_rabbitmq_full_pipeline_with_correlation(self):
        """Test complete RabbitMQ pipeline with user correlation."""
        queue = f"test_pipeline_{generate(size=8)}"
        user_id = f"user_{generate(size=6)}"

        # Set up consumer
        consumer = RabbitMQEventConsumer(
            broker_url="amqp://guest:guest@localhost:5672/", target=queue
        )

        received_events = []

        @consumer.on("start")
        async def handle_start(event: Event):
            received_events.append(("start", event))

        @consumer.on("token")
        async def handle_token(event: Event):
            received_events.append(("token", event))

        @consumer.on("end")
        async def handle_end(event: Event):
            received_events.append(("end", event))

        @consumer.on("error")
        async def handle_error(event: Event):
            received_events.append(("error", event))

        # Start consumer
        consumer_task = asyncio.create_task(consumer.run())
        await asyncio.sleep(0.5)

        # Set up sink
        sink = RabbitMQSink(rabbitmq_url="amqp://guest:guest@localhost:5672/", queue=queue)
        sink.start()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class CorrelatedQA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question, user_id=None):
                with streamll.trace("user_query", user_id=user_id):
                    return self.predict(question=question)

        # Run the instrumented module
        module = CorrelatedQA()
        module(question="What is 2+2?", user_id=user_id)

        sink.stop()

        # Wait for events
        await asyncio.sleep(2.0)

        # Stop consumer
        await consumer.stop()
        consumer_task.cancel()

        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.CancelledError:
            pass

        # Verify events
        event_types = [event_type for event_type, _ in received_events]
        assert "start" in event_types
        assert "end" in event_types

        # Verify correlation data exists and execution IDs are consistent
        execution_ids = {event.execution_id for _, event in received_events}
        assert len(execution_ids) == 1, (
            f"All events should have same execution_id, got: {execution_ids}"
        )

        for event_type, event in received_events:
            assert event.execution_id is not None
            assert event.data.get("user_id") == user_id

    @requires_redis
    @requires_llm
    @pytest.mark.asyncio
    async def test_concurrent_users_correlation(self):
        """Test that events are properly correlated when multiple users run concurrently."""
        stream_key = f"test_concurrent_{generate(size=8)}"

        # Two different users
        user1_id = f"user1_{generate(size=6)}"
        user2_id = f"user2_{generate(size=6)}"
        f"exec1_{generate(size=8)}"
        f"exec2_{generate(size=8)}"

        # Consumer to collect all events
        consumer = RedisEventConsumer(broker_url="redis://localhost:6379", target=stream_key)

        all_events = []

        # Just collect all events in a list
        @consumer.on("start")
        @consumer.on("token")
        @consumer.on("end")
        async def handle_all(event: Event):
            all_events.append(event)

        # Start consumer
        consumer_task = asyncio.create_task(consumer.run())
        await asyncio.sleep(0.5)

        # Set up sink
        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        sink.start()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class QA(dspy.Module):
            def __init__(self):
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question, user_id=None):
                with streamll.trace("user_query", user_id=user_id):
                    return self.predict(question=question)

        # Create module once, reuse for both users
        module = QA()

        # Run both users concurrently
        async def user1_task():
            return module(question="What is 1+1?", user_id=user1_id)

        async def user2_task():
            return module(question="What is 2+2?", user_id=user2_id)

        # Execute concurrently
        await asyncio.gather(user1_task(), user2_task())

        sink.stop()

        # Wait for all events
        await asyncio.sleep(3.0)

        # Stop consumer
        await consumer.stop()
        consumer_task.cancel()

        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.CancelledError:
            pass

        # Verify we got events for both users
        user1_events = [e for e in all_events if e.data.get("user_id") == user1_id]
        user2_events = [e for e in all_events if e.data.get("user_id") == user2_id]

        assert len(user1_events) > 0, "Should have events for user1"
        assert len(user2_events) > 0, "Should have events for user2"

        # Verify each user has consistent execution IDs within their own events
        user1_execution_ids = {e.execution_id for e in user1_events}
        user2_execution_ids = {e.execution_id for e in user2_events}

        assert len(user1_execution_ids) == 1, (
            f"User1 should have one execution_id, got: {user1_execution_ids}"
        )
        assert len(user2_execution_ids) == 1, (
            f"User2 should have one execution_id, got: {user2_execution_ids}"
        )

        # Verify users have different execution IDs (no cross-contamination)
        user1_exec_id = user1_execution_ids.pop()
        user2_exec_id = user2_execution_ids.pop()
        assert user1_exec_id != user2_exec_id, "Users should have different execution IDs"

        # Verify no cross-contamination by user_id
        for event in all_events:
            user_id = event.data.get("user_id")
            if user_id == user1_id:
                assert event.execution_id == user1_exec_id
            elif user_id == user2_id:
                assert event.execution_id == user2_exec_id

    @requires_llm
    @pytest.mark.asyncio
    async def test_error_event_propagation(self):
        """Test that error events are properly captured and propagated."""
        from streamll.sinks.terminal import TerminalSink

        events_captured = []

        class ErrorCapturingSink(TerminalSink):
            def handle_event(self, event):
                events_captured.append(event)
                super().handle_event(event)

        sink = ErrorCapturingSink()
        user_id = f"user_{generate(size=6)}"

        @streamll.instrument(sinks=[sink])
        class ErrorProneQA(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question, user_id=None):
                with streamll.trace("error_test", user_id=user_id):
                    if "error" in question.lower():
                        raise ValueError("Intentional test error")
                    return self.predict(question=question)

        # Test error case
        sink.start()

        with pytest.raises(ValueError, match="Intentional test error"):
            module = ErrorProneQA()
            module(question="Trigger an error please", user_id=user_id)

        sink.stop()

        # Verify error event was captured
        event_types = [e.event_type for e in events_captured]
        assert "start" in event_types
        assert "error" in event_types

        # Verify correlation data in error event
        error_events = [e for e in events_captured if e.event_type == "error"]
        assert len(error_events) > 0

        error_event = error_events[0]
        assert error_event.execution_id is not None
        assert error_event.data.get("user_id") == user_id
        assert "error" in error_event.data
        assert "Intentional test error" in str(error_event.data["error"])

    @requires_redis
    @requires_llm
    @pytest.mark.asyncio
    async def test_streaming_token_reconstruction(self):
        """Test that tokens from consumer can reconstruct the original response."""
        stream_key = f"test_reconstruction_{generate(size=8)}"
        user_id = f"user_{generate(size=6)}"

        # Consumer to collect tokens
        consumer = RedisEventConsumer(broker_url="redis://localhost:6379", target=stream_key)

        collected_tokens = []
        final_answer = None

        @consumer.on("token")
        async def handle_token(event: Event):
            if event.data.get("field") == "answer":
                collected_tokens.append(event.data["token"])

        @consumer.on("end")
        async def handle_end(event: Event):
            nonlocal final_answer
            if "outputs" in event.data:
                # Extract answer from outputs string
                outputs_str = event.data["outputs"]
                if "answer=" in outputs_str:
                    final_answer = outputs_str.split("answer='")[1].split("'")[0]

        # Start consumer
        consumer_task = asyncio.create_task(consumer.run())
        await asyncio.sleep(0.5)

        sink = RedisSink(redis_url="redis://localhost:6379", stream_key=stream_key)
        sink.start()

        @streamll.instrument(sinks=[sink], stream_fields=["answer"])
        class QA(dspy.Module):
            def __init__(self):
                self.predict = dspy.Predict("question -> answer")

            def forward(self, question, user_id=None):
                with streamll.trace("reconstruction_test", user_id=user_id):
                    return self.predict(question=question)

        # Run with a question that should have a predictable answer
        module = QA()
        actual_result = module(question="Count from 1 to 3", user_id=user_id)

        sink.stop()

        # Wait for all events
        await asyncio.sleep(2.0)

        # Stop consumer
        await consumer.stop()
        consumer_task.cancel()

        try:
            await asyncio.wait_for(consumer_task, timeout=2.0)
        except asyncio.CancelledError:
            pass

        # Verify token reconstruction
        assert len(collected_tokens) > 0, "Should have collected streaming tokens"

        reconstructed = "".join(collected_tokens)
        actual_answer = actual_result.answer

        # The reconstructed tokens should contain the actual answer content
        # (may include extra formatting from the model like thinking tokens)
        assert actual_answer in reconstructed or reconstructed.strip() in actual_answer, (
            f"Token reconstruction mismatch.\nTokens: {reconstructed[:100]}...\nActual: {actual_answer}"
        )

        print("✅ Token reconstruction successful!")
        print(f"   Tokens collected: {len(collected_tokens)}")
        print(f"   Reconstructed length: {len(reconstructed)}")
        print(f"   Actual answer: {actual_answer}")
