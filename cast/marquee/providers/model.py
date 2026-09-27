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
        friendly_state = {
            EventState.UPCOMING: "Coming up",
            EventState.STARTING_SOON: "Starting soon",
            EventState.LIVE: "Live now",
            EventState.RESULT: "Result",
            EventState.POST_EVENT: "Recently finished",
            EventState.EXPIRED: "Expired",
        }[self.event_state]
        status = str(raw.get("status", "")).strip()
        # Provider/backend enum tokens are diagnostic data, not card copy.
        # Prefer our human lifecycle wording when a source sends COMING_SOON,
        # STATUS_FINAL, POST_EVENT, or a similar machine label.
        if not status or (status.replace("_", "").isalnum() and
                          status.upper() == status and " " not in status):
            status = friendly_state
        return {
            "id": self.id, "source": self.provider, "provider": self.provider,
            # Priority is the explicit interruption tier. Score remains a
            # diagnostic/refinement value; it must not promote an ordinary
            # provider above a same-tier household context during final display
            # arbitration.
            "type": self.type, "subtype": self.subtype, "priority": self.priority,
            "score": self.score(), "relevance": self.relevance,
            "providerWeight": raw.get("providerWeight", self.priority),
            "urgency": self.urgency, "freshness": self.freshness,
            "significance": self.significance,
            "title": self.title, "subtitle": self.subtitle,
            "detail": self.body, "status": status,
            "accent": self.accent, "starts": value["start_time"],
            "expires": value["expires_at"], "targets": self.targets,
            "left": raw.get("left", {}), "right": raw.get("right", {}),
            "rows": self.stats[:5], "artwork": self.artwork_url,
            "background": self.background_url, "icon": self.icon,
            "sourceUrl": self.source_url, "live": self.live,
            "eventState": self.event_state.value,
            # Optional presentation hints shared by generalized HA calendar
            # providers.  They remain inert for providers that do not publish
            # them and avoid making the browser parse provider descriptions.
            "allDay": bool(raw.get("allDay", raw.get("all_day", False))),
            "location": str(raw.get("location", "")).strip()[:160],
            "castTakeover": bool(raw.get("castTakeover", False)),
            **({"weather": raw["weather"]} if isinstance(raw.get("weather"), dict) else {}),
        }
