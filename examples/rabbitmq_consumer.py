#!/usr/bin/env python
"""Minimal RabbitMQ consumer example."""

import asyncio

from streamll.consumer.rabbitmq import RabbitMQConsumer


async def main():
    consumer = RabbitMQConsumer(
        url="amqp://guest:guest@localhost:5672/",
        exchange="streamll",
        queue="demo",
    )

    @consumer.on("*")
    def handle_event(event):
        pass

    await consumer.start()

    try:
        await consumer.consume_forever()
    except KeyboardInterrupt:
        pass
    finally:
        await consumer.stop()


if __name__ == "__main__":
    asyncio.run(main())
