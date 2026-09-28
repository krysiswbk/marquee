"""Validated versioned attention configuration (JSON; no executable policy)."""

import copy
import json
import math
import re
from dataclasses import fields
from typing import Any

from .conditions import validate_condition
from .models import TIERS, Display
from .targeting import SCENES

DEFAULT: dict[str, Any] = {
    "version": 1,
    "enabled": True,
    "signal_ttl": 90,
    "max_signals": 2000,
    "history_limit": 2000,
    "history_seconds": 604800,
    "switch_margin": 5,
    "context_bindings": {},
    "signal_bindings": [],
    "rules": [
        {
            "id": "weather_alert",
            "match": {"type": "weather", "category": "alert"},
            "active_state": "active",
            "title": "",
            "preferred_scene": "source",
            "escalation": [{"id": "warning", "priority": 80, "urgency": "IMPORTANT"}],
        }
    ],
    "quiet_hours": {"start": 22, "end": 7},
    "displays": [
        {"id": "kiosk", "supports_touch": True},
        {"id": "hubs", "family": "hubs"},
        {"id": "garage", "family": "hubs", "location": "garage"},
    ],
}
RULE: dict[str, Any] = {
    "title": "Household attention",
    "summary": "",
    "match": {},
    "active_state": "on",
    "debounce": 0,
    "cooldown": 300,
    "persistence": "while_active",
    "interruptibility": True,
    "minimum_display_time": 15,
    "maximum_display_time": 0,
    "acknowledgement_required": False,
    "acknowledgement": "reduce",
    "ack_delta": -30,
    "recent_delta": -15,
    "confidence_weight": 20,
    "worsening_seconds": 300,
    "strategy": "global",
    "eligible_displays": [],
    "preferred_scene": "attention",
    "fallback_scene": "attention",
    "grouping_key": "",
    "dedupe_key": "",
    "modifiers": [],
    "escalation": [],
}
STAGE: dict[str, Any] = {"after": 0, "priority": 20, "urgency": "ACTIONABLE"}

# Shared with the admin editor. Keep presentation metadata beside the validator so
# browser constraints cannot drift from the values accepted by the API.
FORM_SCHEMA: dict[str, dict[str, Any]] = {
    "signal_ttl": {"min": 5, "max": 86400, "step": 1, "unit": "seconds", "required": True},
    "switch_margin": {"min": 0, "max": 1000, "step": "any", "unit": "points", "required": True},
    "max_signals": {"min": 1, "max": 10000, "step": 1, "unit": "signals", "required": True},
    "history_limit": {"min": 10, "max": 50000, "step": 1, "unit": "entries", "required": True},
    "history_seconds": {"min": 60, "max": 2592000, "step": 1, "unit": "seconds", "required": True},
    "quiet_hours": {"min": 0, "max": 23, "step": 1, "unit": "hour (0–23)", "required": True},
    "debounce": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "cooldown": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "minimum_display_time": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "maximum_display_time": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "ack_delta": {"min": -1000, "max": 0, "step": "any", "unit": "points", "required": True},
    "recent_delta": {"min": -1000, "max": 0, "step": "any", "unit": "points", "required": True},
    "confidence_weight": {"min": 0, "max": 1000, "step": "any", "unit": "points", "required": True},
    "worsening_seconds": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "stage_after": {"min": 0, "max": 2592000, "step": "any", "unit": "seconds", "required": True},
    "stage_priority": {"min": 0, "max": 1000, "step": "any", "unit": "points", "required": True},
    "modifier_delta": {"min": -1000, "max": 1000, "step": "any", "unit": "points", "required": True},
    "binding_ttl": {"min": 5, "max": 86400, "step": "any", "unit": "seconds", "required": False},
}


def keys(value: Any, allowed: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f"{name}: expected object; unknown fields are not allowed")


def number(value: Any, low: float, high: float, name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"{name} must be a finite number in {low}..{high}")


def string(value: Any, name: str, maximum: int = 500) -> None:
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f"{name} must be a string <= {maximum} characters")


def sequence(value: Any, name: str, maximum: int = 200) -> None:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"{name} must be a list of at most {maximum} entries")


def identifier(value: Any, name: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,120}", value):
        raise ValueError(f"{name} must be a stable identifier")


def validate(value: Any) -> dict[str, Any]:
    json.dumps(value, allow_nan=False)
    keys(value, set(DEFAULT), "attention")
    config = copy.deepcopy(DEFAULT)
    config.update(copy.deepcopy(value))
    if config["version"] != 1 or not isinstance(config["enabled"], bool):
        raise ValueError("attention requires version 1 and boolean enabled")
    for key, low, high in (
        ("signal_ttl", 5, 86400),
        ("max_signals", 1, 10000),
        ("history_limit", 10, 50000),
        ("history_seconds", 60, 2592000),
        ("switch_margin", 0, 1000),
    ):
        number(config[key], low, high, key)
        if key in ("max_signals", "history_limit") and int(config[key]) != config[key]:
            raise ValueError(f"{key} must be an integer")
    quiet = config["quiet_hours"]
    keys(quiet, {"start", "end"}, "quiet_hours")
    if set(quiet) != {"start", "end"}:
        raise ValueError("quiet_hours requires start and end")
    for hour in quiet.values():
        number(hour, 0, 23, "quiet hour")
        if int(hour) != hour:
            raise ValueError("quiet hours must be integer local hours")
    sequence(config["displays"], "displays", 100)
    display_ids: set[str] = set()
    defaults = Display(id="")
    for display in config["displays"]:
        keys(display, {f.name for f in fields(Display)}, "display")
        identifier(display.get("id"), "display.id")
        if display["id"] in display_ids:
            raise ValueError("duplicate display id")
        display_ids.add(display["id"])
        for key, val in display.items():
            if isinstance(getattr(defaults, key), bool):
                if not isinstance(val, bool):
                    raise ValueError(f"display.{key} must be boolean")
            else:
                string(val, f"display.{key}", 120)
        if display.get("family", "kiosk") not in ("hubs", "kiosk"):
            raise ValueError("display family must be kiosk or hubs")
        if display.get("orientation", "landscape") not in ("landscape", "portrait"):
            raise ValueError("invalid orientation")
    sequence(config["signal_bindings"], "signal_bindings", 2000)
    if len(config["signal_bindings"]) * 2 > config["max_signals"]:
        raise ValueError("max_signals must accommodate two signals per HA binding")
    seen: set[str] = set()
    for binding in config["signal_bindings"]:
        keys(binding, {"entity_id", "type", "category", "location", "ttl"}, "signal binding")
        identifier(binding.get("entity_id"), "binding.entity_id")
        if binding["entity_id"] in seen:
            raise ValueError("duplicate signal binding")
        seen.add(binding["entity_id"])
        for key in ("type", "category", "location"):
            if key in binding:
                string(binding[key], key, 120)
        if "ttl" in binding:
            number(binding["ttl"], 5, 86400, "binding.ttl")
    if not isinstance(config["context_bindings"], dict) or len(config["context_bindings"]) > 100:
        raise ValueError("context_bindings must be an object with <= 100 entries")
    for name, binding in config["context_bindings"].items():
        identifier(name, "context name")
        keys(binding, {"entity_id", "values", "attribute", "ttl"}, "context binding")
        identifier(binding.get("entity_id"), "context.entity_id")
        if "attribute" in binding:
            string(binding["attribute"], "attribute", 120)
        if "values" in binding and not isinstance(binding["values"], dict):
            raise ValueError("context values must be an object")
        if "ttl" in binding:
            number(binding["ttl"], 5, 86400, "context.ttl")
    sequence(config["rules"], "rules", 200)
    rule_ids: set[str] = set()
    for index, incoming in enumerate(config["rules"]):
        keys(incoming, set(RULE) | {"id", "resolution_state"}, "rule")
        identifier(incoming.get("id"), "rule.id")
        if incoming["id"] in rule_ids:
            raise ValueError("duplicate rule id")
        rule_ids.add(incoming["id"])
        rule = {**copy.deepcopy(RULE), **incoming}
        config["rules"][index] = rule
        keys(rule["match"], {"type", "source", "category", "entities"}, "match")
        if not rule["match"]:
            raise ValueError("rule.match must restrict the input signals")
        for key, match_value in rule["match"].items():
            if key == "entities":
                sequence(match_value, "match.entities", 2000)
                for entity in match_value:
                    identifier(entity, "match entity")
            else:
                string(match_value, "match value", 120)
        string(rule["active_state"], "active_state")
        if "resolution_state" in rule:
            string(rule["resolution_state"], "resolution_state")
            if rule["resolution_state"] == rule["active_state"]:
                raise ValueError("resolution_state cannot equal active_state")
        for key in ("title", "summary", "grouping_key", "dedupe_key"):
            string(rule[key], key)
        for key in (
            "debounce",
            "cooldown",
            "minimum_display_time",
            "maximum_display_time",
            "worsening_seconds",
        ):
            number(rule[key], 0, 2592000, key)
        for key in ("ack_delta", "recent_delta"):
            number(rule[key], -1000, 0, key)
        number(rule["confidence_weight"], 0, 1000, "confidence_weight")
        if rule["maximum_display_time"] and rule["maximum_display_time"] < rule["minimum_display_time"]:
            raise ValueError("maximum display time must be >= minimum display time")
        if rule["persistence"] not in ("while_active", "timed"):
            raise ValueError("invalid persistence")
        if rule["persistence"] == "timed" and not rule["maximum_display_time"]:
            raise ValueError("timed items require maximum_display_time")
        if rule["acknowledgement"] not in ("reduce", "suppress"):
            raise ValueError("invalid acknowledgement mode")
        for key in ("interruptibility", "acknowledgement_required"):
            if not isinstance(rule[key], bool):
                raise ValueError(f"{key} must be boolean")
        if rule["strategy"] not in ("global", "local", "targeted", "ambient", "critical"):
            raise ValueError("invalid display strategy")
        sequence(rule["eligible_displays"], "eligible_displays", 100)
        if any(d not in display_ids for d in rule["eligible_displays"]):
            raise ValueError("unknown eligible display")
        if rule["strategy"] == "targeted" and not rule["eligible_displays"]:
            raise ValueError("targeted policy requires eligible_displays")
        for key in ("preferred_scene", "fallback_scene"):
            if rule[key] not in SCENES:
                raise ValueError(f"unknown {key}")
        sequence(rule["modifiers"], "modifiers", 100)
        for modifier in rule["modifiers"]:
            keys(modifier, {"id", "when", "delta"}, "modifier")
            identifier(modifier.get("id"), "modifier.id")
            number(modifier.get("delta"), -1000, 1000, "modifier.delta")
            validate_condition(modifier.get("when"))
            if rule["strategy"] in ("global", "critical") and references_display(modifier["when"]):
                raise ValueError("display score modifiers require local, targeted or ambient strategy")
        sequence(rule["escalation"], "escalation", 30)
        if not rule["escalation"]:
            raise ValueError("rule requires at least one escalation stage")
        stage_ids: set[str] = set()
        for stage_index, stage in enumerate(rule["escalation"]):
            keys(stage, set(STAGE) | {"id", "when", "persistence"}, "stage")
            identifier(stage.get("id"), "stage.id")
            if stage["id"] in stage_ids:
                raise ValueError("duplicate stage id")
            stage_ids.add(stage["id"])
            stage = {**STAGE, **stage}
            rule["escalation"][stage_index] = stage
            number(stage["after"], 0, 2592000, "stage.after")
            number(stage["priority"], 0, 1000, "stage.priority")
            if stage["urgency"] not in TIERS:
                raise ValueError("invalid urgency tier")
            if "when" in stage:
                validate_condition(stage["when"])
                if references_display(stage["when"]):
                    raise ValueError("escalation conditions must be display-independent")
            if stage.get("persistence", rule["persistence"]) not in ("while_active", "timed"):
                raise ValueError("invalid stage persistence")
            if stage.get("persistence") == "timed" and not rule["maximum_display_time"]:
                raise ValueError("timed stage requires maximum_display_time")
    return config


def references_display(condition: dict[str, Any]) -> bool:
    if "field" in condition:
        return str(condition["field"]).startswith("display.")
    if "not" in condition:
        return references_display(condition["not"])
    return any(references_display(child) for child in condition.get("all", condition.get("any", [])))
