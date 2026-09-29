"""Policy output and display contracts."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

TIERS = {"AMBIENT": 0, "CONTEXTUAL": 1, "ACTIONABLE": 2, "IMPORTANT": 3, "CRITICAL": 4}


class Lifecycle(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ESCALATED = "ESCALATED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"
    SUPPRESSED = "SUPPRESSED"


@dataclass
class Display:
    id: str
    family: str = "kiosk"
    location: str = ""
    supports_image: bool = True
    supports_video: bool = False
    supports_animation: bool = True
    supports_touch: bool = False
    supports_audio: bool = False
    screen_size: str = "medium"
    orientation: str = "landscape"
    idle_state: bool = True
    user_visible: bool = True
    critical_capable: bool = True
    available: bool = True


@dataclass
class AttentionItem:
    id: str
    signal_id: str
    rule_id: str
    title: str
    summary: str
    priority: float
    urgency: str
    persistence: str
    interruptibility: bool
    minimum_display_time: float
    maximum_display_time: float
    cooldown: float
    acknowledgement_required: bool
    eligible_displays: list[str]
    preferred_scene: str
    fallback_scene: str
    dedupe_key: str
    grouping_key: str
    strategy: str
    location: str
    stage: str
    stage_rank: int
    episode: float
    expires_at: float
    next_escalation_at: float | None
    lifecycle: Lifecycle = Lifecycle.NEW
    acknowledged: bool = False
    score: float = 0
    components: list[dict[str, Any]] = field(default_factory=list)
    suppression: str = ""
    available_at: float | None = None
    members: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)
