"""House context with explicit unknown semantics and configurable mappings."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


class HouseContext:
    def __init__(self, bindings: dict[str, Any], timezone: str, quiet: dict[str, Any], ttl: float) -> None:
        self.bindings, self.timezone, self.quiet, self.ttl = bindings, timezone, quiet, ttl
        self.values: dict[str, tuple[Any, float]] = {}

    def update(self, states: list[dict[str, Any]], now: float, full: bool = False) -> None:
        indexed = {state["entity_id"]: state for state in states}
        for name, binding in self.bindings.items():
            state = indexed.get(binding["entity_id"])
            if state is None:
                if full:
                    self.values.pop(name, None)
                continue
            raw = (
                state.get("attributes", {}).get(binding["attribute"])
                if "attribute" in binding
                else state["state"]
            )
            value = binding["values"].get(str(raw)) if "values" in binding else raw
            if state["state"] in ("unknown", "unavailable", None):
                value = None
            self.values[name] = (value, now + binding.get("ttl", self.ttl))

    def snapshot(self, now: float) -> dict[str, Any]:
        hour = datetime.fromtimestamp(now, ZoneInfo(self.timezone)).hour
        start, end = self.quiet["start"], self.quiet["end"]
        quiet = start <= hour < end if start < end else hour >= start or hour < end
        result = {
            name: self.values[name][0] if name in self.values and self.values[name][1] > now else None
            for name in self.bindings
        }
        result.update(
            hour=hour,
            quiet_hours=quiet if start != end else False,
            time_of_day="night"
            if hour < 6 or hour >= 22
            else "morning"
            if hour < 12
            else "afternoon"
            if hour < 18
            else "evening",
        )
        if isinstance(result.get("home"), bool):
            result["nobody_home"] = not result["home"]
        return result
