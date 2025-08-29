#!/usr/bin/env python
"""Minimal RabbitMQ producer example."""

import streamll
from streamll.sinks.rabbitmq import RabbitMQSink


def main():
    sink = RabbitMQSink(
        url="amqp://guest:guest@localhost:5672/",
        exchange="streamll",
        routing_key="events",
    )
    sink.start()

    with streamll.configure(sinks=[sink]), streamll.trace("demo_operation") as ctx:
        ctx.emit("progress", data={"step": 1})
        ctx.emit("progress", data={"step": 2})

    sink.stop()


if __name__ == "__main__":
    main()
