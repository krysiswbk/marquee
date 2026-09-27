"""Normalized signals and an ordered, bounded observation store."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Signal:
    id: str
    type: str
    source: str
    entity_id: str
    category: str
    state: Any
    created_at: float
    updated_at: float
    active_since: float
    expires_at: float
    severity: float = 0
    priority: float = 0
    confidence: float = 1
    attributes: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    recurrence: int = 1

    def snapshot(self, now: float) -> dict[str, Any]:
        return {**asdict(self), "duration": max(0, now - self.active_since), "fresh": self.expires_at > now}


class SignalStore:
    def __init__(self, limit: int = 2000) -> None:
        self.values: dict[str, Signal] = {}
        self.limit = limit

    def observe(self, signal: Signal, now: float) -> bool:
        old = self.values.get(signal.id)
        if old and signal.updated_at <= old.updated_at:
            return False
        if old:
            signal.created_at = old.created_at
            same = old.state == signal.state and old.expires_at > now
            signal.active_since = old.active_since if same else now
            signal.recurrence = old.recurrence if same else min(1000, old.recurrence + 1)
        else:
            # A new adapter cannot assert an unverified historical duration.
            signal.active_since = now
        if not old and len(self.values) >= self.limit:
            expired = [key for key, value in self.values.items() if value.expires_at <= now]
            if not expired:
                raise ValueError("signal capacity reached")
            del self.values[expired[0]]
        changed = old is None or old.state != signal.state or old.attributes != signal.attributes
        self.values[signal.id] = signal
        return changed

    def prune(self, now: float, retention: float) -> None:
        for key in list(self.values):
            if self.values[key].expires_at + retention <= now:
                del self.values[key]
