from streamll.models import Event


class EventCapturingSink:
    def __init__(self):
        self.events = []
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def handle_event(self, event: Event) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()
