"""streamll - Production Streaming Infrastructure for DSPy.

Transform black-box LLM pipelines into observable, real-time systems.
"""

__version__ = "0.1.0"

# Core functionality imports
from streamll.context import configure, emit, emit_event, trace
from streamll.decorator import instrument
from streamll.models import StreamllEvent
from streamll.streaming import create_streaming_wrapper

# Public API
__all__ = [
    # Configuration
    "configure",
    # Event emission
    "emit",
    "emit_event",
    "StreamllEvent",
    # Instrumentation
    "instrument",
    "trace",
    # Streaming
    "create_streaming_wrapper",
]
