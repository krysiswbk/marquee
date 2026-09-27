"""Explainable scoring and stage selection; callers supply the clock/context."""

from typing import Any

from ..signals.model import Signal
from .conditions import matches
from .models import TIERS


def stage_for(rule: dict[str, Any], env: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    eligible = [
        (stage, index)
        for index, stage in enumerate(rule["escalation"])
        if env["signal"]["duration"] >= stage["after"] and matches(stage.get("when"), env)
    ]
    return max(
        eligible,
        key=lambda pair: (TIERS[pair[0]["urgency"]], pair[0]["priority"], pair[0]["after"], pair[1]),
        default=(None, -1),
    )


def score(
    rule: dict[str, Any], stage: dict[str, Any], env: dict[str, Any], acknowledged: bool, recent: bool
) -> tuple[float, list[dict[str, Any]]]:
    components: list[dict[str, Any]] = [{"reason": f"stage: {stage['id']}", "delta": stage["priority"]}]
    for modifier in rule["modifiers"]:
        if matches(modifier["when"], env):
            components.append({"reason": modifier["id"], "delta": modifier["delta"]})
    for reason, delta in (
        ("confidence", -(1 - env["signal"]["confidence"]) * rule["confidence_weight"]),
        ("acknowledged", rule["ack_delta"] if acknowledged else 0),
        ("recently displayed", rule["recent_delta"] if recent else 0),
    ):
        if delta:
            components.append({"reason": reason, "delta": delta})
    return sum(float(part["delta"]) for part in components), components


def accepts(rule: dict[str, Any], signal: Signal) -> bool:
    match = rule["match"]
    return all(getattr(signal, key) == value for key, value in match.items() if key != "entities") and (
        "entities" not in match or signal.entity_id in match["entities"]
    )
