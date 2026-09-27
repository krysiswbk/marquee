"""Adapt configured HA state snapshots; integrations do not decide priority."""

from typing import Any

from .model import Signal


def normalize(
    states: list[dict[str, Any]], bindings: list[dict[str, Any]], now: float, ttl: float
) -> list[Signal]:
    indexed = {state["entity_id"]: state for state in states}
    result = []
    for binding in bindings:
        entity = binding["entity_id"]
        state = indexed.get(entity)
        if state is None:
            continue
        attributes = dict(state.get("attributes", {}))
        attributes["location"] = binding.get("location", attributes.get("location", ""))
        unavailable = state["state"] in ("unavailable", "unknown", None)
        result.append(
            Signal(
                id=f"ha:{entity}",
                source="home_assistant",
                entity_id=entity,
                type=binding.get("type", entity.split(".")[0]),
                category=binding.get("category", "household"),
                state=state["state"],
                created_at=now,
                updated_at=now,
                active_since=now,
                expires_at=now if unavailable else now + binding.get("ttl", ttl),
                confidence=0 if unavailable else 1,
                attributes=attributes,
                dedupe_key=entity,
            )
        )
        result.append(
            Signal(
                id=f"ha-health:{entity}",
                type="availability",
                source="home_assistant",
                entity_id=entity,
                category="sensor_health",
                state="unavailable" if unavailable else "available",
                created_at=now,
                updated_at=now,
                active_since=now,
                expires_at=now + binding.get("ttl", ttl),
                attributes=attributes,
                dedupe_key=f"health:{entity}",
            )
        )
    return result
