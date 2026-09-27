"""Capability selection independent of device model or integration."""

from dataclasses import asdict
from typing import Any

from .models import AttentionItem, Display

SCENES: dict[str, list[str]] = {
    "attention": [],
    "source": ["supports_image"],
    "image": ["supports_image"],
    "radar": ["supports_image", "supports_animation"],
}


def target(item: AttentionItem, display: Display, scenes: dict[str, list[str]]) -> tuple[str | None, str]:
    if not display.available:
        return None, "display unavailable"
    critical = item.urgency == "CRITICAL" or item.strategy == "critical"
    if critical and not display.critical_capable:
        return None, "display cannot present critical items"
    if not critical:
        if not display.user_visible:
            return None, "display not visible"
        if item.eligible_displays and display.id not in item.eligible_displays:
            return None, "outside eligible displays"
        if item.strategy == "local" and (not item.location or item.location != display.location):
            return None, "outside event location"
        if item.strategy == "ambient" and not display.idle_state:
            return None, "display busy"
    capabilities: dict[str, Any] = asdict(display)
    for scene in (item.preferred_scene, item.fallback_scene):
        if all(capabilities.get(capability) for capability in scenes[scene]):
            return scene, "critical broadcast" if critical else item.strategy
    if critical:
        return "attention", "critical universal text fallback"
    return None, "no compatible renderer"
