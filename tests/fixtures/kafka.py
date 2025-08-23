"""Test fixtures and utilities for Kafka/Redpanda testing.

Following Diamond Approach patterns for test infrastructure.
"""

import asyncio
import json
import os
import time
from collections.abc import Generator
from contextlib import contextmanager

import pytest


class KafkaTestClient:
    """Test client wrapper for Kafka/Redpanda operations."""

    def __init__(self, bootstrap_servers: str = None):
        """Initialize test client."""
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
        )
        self.producer = None
        self.consumer = None
        self._loop = None
        self._topics_created = set()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Connect to Kafka/Redpanda."""
        try:
            from aiokafka import AIOKafkaProducer

            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            await self.producer.start()

        except Exception as e:
            raise ConnectionError(f"Failed to connect to Kafka: {e}")

    async def disconnect(self):
        """Disconnect from Kafka/Redpanda."""
        if self.producer:
            await self.producer.stop()
            self.producer = None

        if self.consumer:
            await self.consumer.stop()
            self.consumer = None

    async def send_message(self, topic: str, value: dict, key: str = None) -> None:
        """Send message to Kafka topic."""
        if not self.producer:
            await self.connect()

        key_bytes = key.encode('utf-8') if key else None
        await self.producer.send(topic, value=value, key=key_bytes)

    async def consume_messages(
        self,
        topic: str,
        group_id: str = None,
        max_messages: int = 10,
        timeout_ms: int = 5000
    ) -> list[dict]:
        """Consume messages from Kafka topic."""
        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id or f"test_{int(time.time()*1000)}",
                auto_offset_reset="earliest",
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            await consumer.start()

            messages = []
            try:
                # Get messages with timeout
                msg_batch = await consumer.getmany(
                    timeout_ms=timeout_ms,
                    max_records=max_messages
                )

                for partition, msgs in msg_batch.items():
                    for msg in msgs:
                        messages.append(msg.value)

            finally:
                await consumer.stop()

            return messages

        except Exception as e:
            raise RuntimeError(f"Failed to consume messages: {e}")

    async def create_topic(
        self,
        topic_name: str,
        num_partitions: int = 1,
        replication_factor: int = 1
    ) -> bool:
        """Create Kafka topic."""
        try:
            from aiokafka.admin import AIOKafkaAdminClient, NewTopic

            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers
            )
            await admin.start()

            try:
                topic = NewTopic(
                    name=topic_name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor
                )

                await admin.create_topics([topic])
                self._topics_created.add(topic_name)
                return True

            finally:
                await admin.close()

        except Exception:
            return False  # Topic might already exist

    async def delete_topic(self, topic_name: str) -> bool:
        """Delete Kafka topic."""
        try:
            from aiokafka.admin import AIOKafkaAdminClient

            admin = AIOKafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers
            )
            await admin.start()

            try:
                await admin.delete_topics([topic_name])
                self._topics_created.discard(topic_name)
                return True

            finally:
                await admin.close()

        except Exception:
            return False

    async def cleanup(self):
        """Clean up test topics."""
        for topic in list(self._topics_created):
            await self.delete_topic(topic)

    def ping(self) -> bool:
        """Test Kafka connectivity synchronously."""
        try:
            import socket

            host, port = self.bootstrap_servers.split(':')
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            return result == 0

        except Exception:
            return False


class KafkaInfrastructureTester:
    """Test utilities for Kafka infrastructure."""

    @staticmethod
    def is_available(host: str = "localhost", port: int = 9092) -> bool:
        """Check if Kafka/Redpanda is available."""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    @staticmethod
    async def wait_for_connection(
        client: KafkaTestClient,
        max_retries: int = 10,
        delay: float = 0.5
    ) -> bool:
        """Wait for Kafka connection to be available."""
        for _ in range(max_retries):
            if client.ping():
                return True
            await asyncio.sleep(delay)
        return False

    @staticmethod
    @contextmanager
    def simulate_connection_failure(client: KafkaTestClient) -> Generator[None, None, None]:
        """Simulate Kafka connection failure for resilience testing."""
        original_servers = client.bootstrap_servers
        try:
            # Point to invalid server
            client.bootstrap_servers = "invalid-broker:9092"
            yield
        finally:
            # Restore original
            client.bootstrap_servers = original_servers


@pytest.fixture(scope="session")
def kafka_test_client():
    """Provide Kafka test client for integration tests."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    # Check if Kafka is available
    if not KafkaInfrastructureTester.is_available():
        pytest.skip("Kafka/Redpanda not available for testing")

    return KafkaTestClient(bootstrap_servers)


@pytest.fixture
async def kafka_client(kafka_test_client):
    """Provide connected Kafka client for tests."""
    async with kafka_test_client as client:
        yield client


@pytest.fixture
def isolated_kafka_topic(kafka_test_client):
    """Create isolated Kafka topic for test."""
    topic_name = f"test_{int(time.time()*1000)}_{id(object())}"

    async def create():
        await kafka_test_client.create_topic(topic_name)
        return topic_name

    # Run async creation
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create())

    yield topic_name

    # Cleanup
    async def cleanup():
        await kafka_test_client.delete_topic(topic_name)

    loop.run_until_complete(cleanup())
    loop.close()


@pytest.fixture
def kafka_sink_factory():
    """Factory for creating test Kafka sinks."""
    from streamll.sinks.kafka import KafkaSink

    created_sinks = []

    def _create_sink(**kwargs):
        """Create Kafka sink with test defaults."""
        defaults = {
            "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            "topic": f"test_sink_{int(time.time()*1000)}",
            "batch_size": 10,
            "batch_timeout_ms": 100,
            "circuit_breaker": True,
            "failure_threshold": 3,
            "recovery_timeout": 1.0,
        }
        defaults.update(kwargs)

        sink = KafkaSink(**defaults)
        created_sinks.append(sink)
        return sink

    yield _create_sink

    # Cleanup all created sinks
    for sink in created_sinks:
        if sink.is_running:
            sink.stop()


# Test data generators
def generate_test_events(count: int = 10) -> list[dict]:
    """Generate test event data."""
    events = []
    for i in range(count):
        events.append({
            "event_id": f"test_{i}_{int(time.time()*1000)}",
            "execution_id": f"exec_{i % 3}",  # Group into 3 executions
            "timestamp": time.time(),
            "module_name": f"module_{i % 2}",
            "method_name": f"method_{i % 4}",
            "event_type": "test",
            "operation": f"op_{i % 5}",
            "data": {
                "index": i,
                "value": i * 10,
                "category": f"cat_{i % 3}"
            },
            "tags": {
                "test": "true",
                "batch": str(i // 10)
            }
        })
    return events


def verify_event_order(events: list[dict]) -> bool:
    """Verify events are in expected order."""
    last_index = -1
    for event in events:
        if "index" in event.get("data", {}):
            index = event["data"]["index"]
            if index <= last_index:
                return False
            last_index = index
    return True


def verify_event_integrity(original: dict, received: dict) -> bool:
    """Verify event data integrity."""
    # Check required fields
    required_fields = ["event_id", "execution_id", "timestamp", "data"]
    for field in required_fields:
        if field not in received:
            return False
        if field != "timestamp" and original[field] != received[field]:
            return False

    # Check data integrity
    if original.get("data") != received.get("data"):
        return False

    return True
