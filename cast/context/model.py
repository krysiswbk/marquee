from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventState(str, Enum):
    UPCOMING = "UPCOMING"
    STARTING_SOON = "STARTING_SOON"
    LIVE = "LIVE"
    RESULT = "RESULT"
    POST_EVENT = "POST_EVENT"
    EXPIRED = "EXPIRED"


def utcnow():
    return datetime.now(timezone.utc)


def parse_time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@dataclass
class Context:
    id: str
    provider: str
    type: str
    title: str
    subtype: str = ""
    subtitle: str = ""
    body: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    event_state: EventState = EventState.UPCOMING
    priority: int = 40
    relevance: int = 50
    urgency: int = 50
    freshness: int = 100
    significance: int = 50
    artwork_url: str = ""
    background_url: str = ""
    icon: str = ""
    accent: str = ""
    live: bool = False
    expires_at: datetime | None = None
    refresh_after: datetime | None = None
    source_url: str = ""
    targets: list[str] = field(default_factory=lambda: ["kiosk"])
    stats: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def expired(self, now=None):
        now = now or utcnow()
        return self.event_state == EventState.EXPIRED or bool(
            self.expires_at and self.expires_at <= now)

    def score(self):
        """Deterministic arbitration: explicit tier dominates, factors refine it."""
        adjustment = ((self.relevance - 50) * .12 + (self.urgency - 50) * .08
                      + (self.significance - 50) * .06 + (self.freshness - 50) * .04)
        return round(max(0, min(100, self.priority + adjustment)), 2)

    def to_dict(self):
        value = asdict(self)
        value["event_state"] = self.event_state.value
        value["score"] = self.score()
        for key in ("start_time", "end_time", "expires_at", "refresh_after"):
            item = value[key]
            value[key] = item.astimezone(timezone.utc).isoformat() if item else ""
        return value

    def display_dict(self):
        """Compatibility shape consumed by the existing generic/sports renderer."""
        value = self.to_dict()
        raw = self.raw or {}
        return {
            "id": self.id, "source": self.provider, "provider": self.provider,
            "type": self.type, "subtype": self.subtype, "priority": int(self.score()),
            "score": self.score(), "title": self.title, "subtitle": self.subtitle,
            "detail": self.body, "status": raw.get("status", self.event_state.value),
            "accent": self.accent, "starts": value["start_time"],
            "expires": value["expires_at"], "targets": self.targets,
            "left": raw.get("left", {}), "right": raw.get("right", {}),
            "rows": self.stats[:5], "artwork": self.artwork_url,
            "background": self.background_url, "icon": self.icon,
            "sourceUrl": self.source_url, "live": self.live,
            "eventState": self.event_state.value,
        }
