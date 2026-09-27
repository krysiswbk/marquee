"""Small synchronous in-process event bus used for observability hooks."""
from collections import defaultdict
from threading import RLock


class EventBus:
    def __init__(self):
        self._handlers = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event, callback):
        with self._lock:
            self._handlers[event].append(callback)
        return lambda: self.unsubscribe(event, callback)

    def unsubscribe(self, event, callback):
        with self._lock:
            if callback in self._handlers[event]:
                self._handlers[event].remove(callback)

    def publish(self, event, **payload):
        with self._lock:
            handlers = tuple(self._handlers[event])
        for handler in handlers:
            handler(event, payload)
