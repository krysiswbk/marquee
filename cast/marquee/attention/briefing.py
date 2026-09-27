"""Household editorial view: observed facts and short-lived activity, not alarms."""
from typing import Any, Iterable

from ..signals.model import Signal

HOUSE_CATEGORIES = {"exterior_door", "garage_door", "door_lock", "window", "visitor", "fire_alert"}
SUPPORT_TYPES = {"calendar_event", "house_summary", "gaming", "tv_release", "astronomy"}


def supporting(item: dict[str, Any]) -> bool:
    """Routine information belongs on the desk, never in its scene rotation."""
    if str(item.get("id", "")).startswith("screen-test:"):
        return False
    return item.get("type") in SUPPORT_TYPES or (
        item.get("type") == "weather" and item.get("subtype") == "current")


def label(signal: Signal) -> str:
    if signal.category == "door_lock":
        return "Front door lock" if signal.attributes.get("location") == "entrance" else str(signal.attributes.get("friendly_name", "Door lock"))
    return str(signal.attributes.get("friendly_name") or signal.entity_id.replace("_", " ").split(".")[-1])


def transition(old: Signal | None, new: Signal, now: float) -> dict[str, Any] | None:
    # A startup snapshot or reconnect is not evidence that someone touched a door.
    if not old or old.expires_at <= now or new.expires_at <= now or old.state == new.state:
        return None
    if new.category not in HOUSE_CATEGORIES:
        return None
    if new.category == "door_lock":
        verb = {"unlocked": "unlocked", "locked": "locked"}.get(new.state)
    elif new.category == "visitor":
        verb = "Person at the front door" if new.state == "on" else None
    elif new.category == "fire_alert":
        return None  # Safety policy owns this presentation.
    else:
        verb = {"on": "opened", "off": "closed"}.get(new.state)
    if not verb:
        return None
    return {"id": f"{new.id}:{now}", "at": now, "expires": now + 900,
            "entity_id": new.entity_id, "category": new.category,
            "title": verb if new.category == "visitor" else f"{label(new)} {verb}",
            "tone": "amber" if verb in ("unlocked", "opened") else "mint"}


def build(store: dict[str, Signal], house: dict[str, Any], events: Iterable[dict[str, Any]],
          now: float, observed: float, ttl: float) -> dict[str, Any]:
    fresh = observed > 0 and now - observed < ttl
    signals = [s for s in store.values() if s.id.startswith("ha:") and s.category in HOUSE_CATEGORIES]
    openings: list[dict[str, Any]] = []
    for s in signals:
        if s.expires_at <= now:
            continue
        if s.category in ("exterior_door", "garage_door", "window") and s.state == "on" or s.category == "door_lock" and s.state == "unlocked":
            openings.append({"id": s.id, "name": label(s), "category": s.category,
                             "state": "unlocked" if s.category == "door_lock" else "open",
                             "since": s.active_since, "duration": max(0, now-s.active_since)})
    openings.sort(key=lambda s: (s["category"] == "window", -s["duration"]))
    unknown = [label(s) for s in signals if s.expires_at <= now]
    device_health = [{"entity_id": s.entity_id, "name": label(s),
                      "location": s.attributes.get("location"),
                      "state": "unavailable", "since": s.active_since}
                     for s in store.values()
                     if fresh and s.id.startswith("ha-health:")
                     and s.attributes.get("location") == "nursery"
                     and s.state == "unavailable" and s.expires_at > now
                     and now - s.active_since >= 60]
    device_health.sort(key=lambda item: str(item["name"]))
    people = [{"name": name, "state": house.get(key) or "Unknown"}
              for name, key in (("Kris", "kris_status"), ("Magda", "magda_status"), ("Max", "maxson_status"))
              if key in house]
    contexts = [s.attributes for s in store.values() if s.id.startswith("context:") and s.expires_at > now]
    cards = [c for c in contexts if supporting(c) and c.get("type") != "house_summary"]
    cards.sort(key=lambda c: (c.get("subtype") != "birthday_rollup",
                              str(c.get("starts") or "9999"),
                              str(c.get("id", ""))))
    return {"at": now, "fresh": fresh, "source_at": observed, "openings": openings,
            "unknown": unknown, "device_health": device_health, "people": people,
            "events": [e for e in reversed(list(events)) if e["expires"] > now] if fresh else [],
            "cards": cards[:30], "network": house.get("network_health"),
            "sleeping": house.get("someone_sleeping"), "guests": house.get("guests"),
            "garage_occupied": house.get("garage_occupied"), "weather_state": house.get("weather_state"),
            "lock": next((s.state for s in signals if s.category == "door_lock" and s.expires_at > now), None)}
