"""Terminal sink for development and debugging.

Pretty-prints events to the terminal with optional rich formatting.
"""

import asyncio
import json
import sys
from typing import TextIO

from streamll.models import StreamllEvent
from streamll.sinks.base import BaseSink


class TerminalSink(BaseSink):
    """Sink that outputs events to terminal/console.

    Useful for development and debugging. Can use rich formatting
    if available, otherwise falls back to simple printing.
    """

    def __init__(
        self,
        output: TextIO = sys.stdout,
        use_rich: bool = True,
        show_timestamp: bool = True,
        show_data: bool = True,
        show_module: bool = True,
        indent: int = 2,
    ):
        """Initialize terminal sink.

        Args:
            output: Output stream (default: stdout)
            use_rich: Whether to use rich formatting if available
            show_timestamp: Whether to show event timestamps
            show_data: Whether to show event data payload
            show_module: Whether to show module names for multi-module debugging
            indent: JSON indentation for data
        """
        super().__init__(buffer_size=1, batch_size=1, flush_interval=0)
        self.output = output
        self.use_rich = use_rich
        self.show_timestamp = show_timestamp
        self.show_data = show_data
        self.show_module = show_module
        self.indent = indent

        # Thread-safe event queue for multi-module support
        self.event_queue: asyncio.Queue | None = None
        self._background_task: asyncio.Task | None = None

        # Try to import rich if requested
        self.rich_console = None
        if use_rich:
            try:
                from rich.console import Console

                self.rich_console = Console(file=output)
            except ImportError:
                # Fall back to simple printing
                pass

    def start(self) -> None:
        """Start the terminal sink.

        Sets up asyncio queue for thread-safe multi-module event handling.
        """
        self.is_running = True
        # self.event_queue = asyncio.Queue(maxsize=1000)
        # self._background_task = asyncio.create_task(self._process_events())
        pass

    def stop(self) -> None:
        """Stop the terminal sink.

        Flush any remaining output and clean up async resources.
        """
        self.is_running = False
        # if self._background_task: self._background_task.cancel()
        # if self.event_queue: drain remaining events
        self.output.flush()

    def handle_event(self, event: StreamllEvent) -> None:
        """Handle a single event by queuing it for async processing.

        Args:
            event: The event to print
        """
        if not self.is_running:
            return

        # For multi-module support, queue events for ordered processing
        # if self.event_queue: self.event_queue.put_nowait(event)
        # else: self._print_event_sync(event)  # Fallback for sync usage

        # Temporary direct printing for wireframe
        if self.rich_console:
            self._print_rich(event)
        else:
            self._print_simple(event)
        self.output.flush()

    def flush(self) -> None:
        """Flush output stream.

        Terminal sink doesn't buffer, so just flush stream.
        """
        self.output.flush()

    def _print_rich(self, event: StreamllEvent) -> None:
        """Print event using rich formatting.

        Args:
            event: Event to print with rich
        """

        # Build formatted output
        parts = []

        # Timestamp with color
        if self.show_timestamp:
            ts = event.timestamp.strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
            parts.append(f"[dim cyan][{ts}][/dim cyan]")

        # Event type with colored symbol and operation
        symbols_and_colors = {
            "start": ("▶", "green"),
            "end": ("■", "blue"),
            "error": ("✗", "red bold"),
            "token": ("•", "cyan"),
        }
        symbol, color = symbols_and_colors.get(event.event_type, ("?", "yellow"))
        op_name = event.operation or "unknown"

        parts.append(f"[{color}]{symbol}[/{color}] [bold]{op_name}[/bold]")

        # Module name if present
        if self.show_module and event.tags.get("module_name"):
            module = event.tags["module_name"]
            parts.append(f"[magenta]\\[{module}][/magenta]")

        # Execution ID (abbreviated)
        if event.execution_id:
            exec_id = event.execution_id[:8] if len(event.execution_id) > 8 else event.execution_id
            parts.append(f"[dim]({exec_id})[/dim]")

        # Main header line
        header = " ".join(parts)

        # Format data if present and requested
        if self.show_data and event.data:
            # Special handling for different event types
            if event.event_type == "error":
                # Error formatting
                error_msg = event.data.get("error", "Unknown error")
                error_type = event.data.get("error_type", "Error")
                self.rich_console.print(f"{header}")
                self.rich_console.print(f"  [red]└─ {error_type}: {error_msg}[/red]")
            elif event.event_type == "token" and "token" in event.data:
                # Token display with newlines for better readability
                token = event.data["token"]
                self.rich_console.print(f"{header} [cyan]{repr(token)}[/cyan]")
            elif event.operation in ["llm_call", "tool_call"]:
                # LLM/Tool calls get special treatment
                self.rich_console.print(header)

                # Extract key fields for pretty display
                if "prompt" in event.data:
                    prompt = event.data["prompt"]
                    if len(prompt) > 200:
                        prompt = prompt[:197] + "..."
                    self.rich_console.print(f"  [dim]├─ prompt:[/dim] {prompt}")

                if "completion" in event.data:
                    completion = event.data["completion"]
                    if len(completion) > 200:
                        completion = completion[:197] + "..."
                    self.rich_console.print(
                        f"  [dim]├─ completion:[/dim] [green]{completion}[/green]"
                    )

                if "tool_name" in event.data:
                    self.rich_console.print(
                        f"  [dim]├─ tool:[/dim] [yellow]{event.data['tool_name']}[/yellow]"
                    )

                if "arguments" in event.data:
                    args_str = json.dumps(event.data["arguments"], indent=None)
                    if len(args_str) > 100:
                        args_str = args_str[:97] + "..."
                    self.rich_console.print(f"  [dim]├─ args:[/dim] {args_str}")

                # Token usage if present
                if any(k.endswith("_tokens") for k in event.data):
                    tokens = []
                    for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
                        if key in event.data:
                            tokens.append(f"{key.split('_')[0]}: {event.data[key]}")
                    if tokens:
                        self.rich_console.print(f"  [dim]└─ tokens:[/dim] {', '.join(tokens)}")
            else:
                # Generic data display
                self.rich_console.print(header)

                # Pretty print JSON data
                data_str = json.dumps(event.data, indent=2)
                if len(data_str) > 500:
                    data_str = json.dumps(event.data, indent=None)[:497] + "..."

                # Indent the data
                for line in data_str.split("\n"):
                    self.rich_console.print(f"  [dim]{line}[/dim]")
        else:
            # Just print the header if no data
            self.rich_console.print(header)

    def _print_simple(self, event: StreamllEvent) -> None:
        """Print event using simple formatting.

        Format: [timestamp] SYMBOL operation_name: {"data": "..."}
        Example: [10:30:45] ▶ module_forward: {"question": "What is DSPy?"}
        """
        parts = []

        # Add timestamp if requested
        if self.show_timestamp:
            ts = event.timestamp.strftime("%H:%M:%S")
            parts.append(f"[{ts}]")

        # Add event type symbol and operation
        symbols = {"start": "▶", "end": "■", "error": "✗", "token": "•"}
        symbol = symbols.get(event.event_type, "?")
        op_name = event.operation or "unknown"
        parts.append(f"{symbol} {op_name}")

        # Add module name for multi-module debugging
        if self.show_module and event.tags.get("module_name"):
            module = event.tags["module_name"]
            parts.append(f"[{module}]")

        # Add data if requested and not empty
        if self.show_data and event.data:
            data_json = json.dumps(event.data, indent=None)
            if len(data_json) > 100:
                data_json = data_json[:97] + "..."
            parts.append(f": {data_json}")

        # Write formatted line
        line = " ".join(parts)
        self.output.write(line + "\n")
