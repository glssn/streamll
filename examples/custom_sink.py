#!/usr/bin/env python
"""Example of creating a custom sink."""

import dspy

import streamll
from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink


class FileSink(BaseSink):
    """Simple sink that writes events to a file."""

    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        self.file = None

    def start(self):
        self.is_running = True
        self.file = open(self.filename, "a")  # noqa: SIM115

    def stop(self):
        self.is_running = False
        if self.file:
            self.file.close()

    def handle_event(self, event: StreamllEvent):
        if self.file and self.is_running:
            self.file.write(f"{event.model_dump_json()}\n")
            self.file.flush()

    def flush(self):
        if self.file:
            self.file.flush()

    def _write_batch(self, batch):
        """Write batch of events - not used since we write immediately."""
        pass


# Use custom sink
file_sink = FileSink("events.jsonl")
streamll.configure(sinks=[file_sink])


@streamll.instrument
class SimpleModule(dspy.Module):
    def forward(self, x):
        return {"result": x * 2}


# Events will be written to events.jsonl
module = SimpleModule()
module(5)
