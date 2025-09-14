from streamll.sinks.terminal import TerminalSink

__all__ = ["TerminalSink"]

try:
    from streamll.sinks.redis import RedisSink
    __all__ += ["RedisSink"]
except ImportError:
    pass

try:
    from streamll.sinks.rabbitmq import RabbitMQSink
    __all__ += ["RabbitMQSink"]
except ImportError:
    pass