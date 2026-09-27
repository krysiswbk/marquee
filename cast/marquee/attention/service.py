"""Thread-safe application boundary for the deterministic attention engine."""

import json
import os
import threading
import time
from collections import deque
from typing import Any, Callable

from ..context.provider import HouseContext
from ..signals.contexts import normalize as context_signal
from ..signals.home_assistant import normalize as ha_signals
from ..signals.model import SignalStore
from .briefing import build, transition
from .history import History
from .manager import AttentionManager
from .presentation import present
from .schema import validate


class AttentionService:
    def __init__(self, config: dict[str, Any], data_dir: str, clock: Callable[[], float] = time.time) -> None:
        self.lock = threading.RLock()
        self.clock, self.data_dir = clock, data_dir
        self.baselines: dict[str, dict[str, Any] | None] = {}
        self._source_sequence: float = -1
        self.history: History
        self.configure(config)

    def configure(self, config: dict[str, Any]) -> None:
        validated = validate(config.get("attention", {}))
        with self.lock:
            if hasattr(self, "history"):
                self.history.close()
            self.config = validated
            self.history = History(
                os.path.join(self.data_dir, "attention-history.sqlite3"),
                int(validated["history_limit"]),
                validated["history_seconds"],
            )
            self.store = SignalStore(int(validated["max_signals"]))
            self.activity: deque[dict[str, Any]] = deque(maxlen=80)
            self.house = HouseContext(
                validated["context_bindings"],
                config.get("general", {}).get("timezone", "UTC"),
                validated["quiet_hours"],
                validated["signal_ttl"],
            )
            self.manager = AttentionManager(validated, self.store, self.history, self.clock())
            self._source_sequence = -1
            self.history.record(self.clock(), "configuration", rules=len(validated["rules"]))

    def ingest(self, body: dict[str, Any]) -> None:
        from .schema import keys, number, sequence, string

        json.dumps(body, allow_nan=False)
        keys(body, {"states", "full", "observed_at"}, "HA snapshot")
        sequence(body.get("states"), "states", 2000)
        if not isinstance(body.get("full", False), bool):
            raise ValueError("full must be boolean")
        now = self.clock()
        observed = body.get("observed_at", now)
        number(observed, now - self.config["signal_ttl"], now + 5, "observed_at")
        # Validate the entire batch before mutating any source state.
        seen: set[str] = set()
        for state in body["states"]:
            keys(state, {"entity_id", "state", "attributes"}, "state")
            string(state.get("entity_id"), "entity_id", 120)
            if state["entity_id"] in seen:
                raise ValueError("duplicate state entity")
            seen.add(state["entity_id"])
            string(state.get("state"), "state", 500)
            if not isinstance(state.get("attributes", {}), dict):
                raise ValueError("attributes must be an object")
        with self.lock:
            if observed <= self._source_sequence:
                raise ValueError("out-of-order HA snapshot")
            states = body["states"]
            signals = ha_signals(states, self.config["signal_bindings"], now, self.config["signal_ttl"])
            new_ids = {s.id for s in signals} - set(self.store.values)
            capacity = len([s for s in self.store.values.values() if s.expires_at > now])
            if capacity + len(new_ids) > self.store.limit:
                raise ValueError("signal capacity reached")
            self._source_sequence = observed
            for signal in signals:
                signal.expires_at -= now - observed
                event = transition(self.store.values.get(signal.id), signal, now)
                if self.store.observe(signal, now):
                    if event:
                        self.activity.append(event)
                    self.history.record(now, "signal", id=signal.id, state=signal.state)
            if body.get("full"):
                present_ids = {s.id for s in signals}
                for signal in self.store.values.values():
                    if signal.source == "home_assistant" and signal.id not in present_ids:
                        signal.expires_at = now
            self.house.update(states, observed, body.get("full", False))
            self._refresh(now)

    def sync_contexts(self, contexts: list[dict[str, Any]], media: dict[str, Any] | None) -> None:
        now = self.clock()
        with self.lock:
            seen: set[str] = set()
            values = contexts + (
                [
                    {
                        "id": "plex:now",
                        "type": "media",
                        "source": "media",
                        "title": media.get("title", "Media playing"),
                        "priority": 15,
                    }
                ]
                if media
                else []
            )
            for value in values:
                signal = context_signal(value, now)
                seen.add(signal.id)
                try:
                    if self.store.observe(signal, now):
                        self.history.record(now, "signal", id=signal.id, state=signal.state)
                except ValueError:
                    # Keep an overloaded provider from starving household ingestion.
                    continue
            for signal in self.store.values.values():
                if signal.id.startswith("context:") and signal.id not in seen:
                    signal.expires_at = now
            self._refresh(now)

    def _refresh(self, now: float) -> None:
        context = self.house.snapshot(now)
        context.setdefault(
            "active_media", any(s.type == "media" and s.expires_at > now for s in self.store.values.values())
        )
        self.manager.refresh(context, now)

    def choose(
        self, display: str, baseline: dict[str, Any] | None, interacting: bool = False
    ) -> dict[str, Any] | None:
        with self.lock:
            now = self.clock()
            self.baselines[display] = baseline
            if not self.config["enabled"]:
                return None
            self._refresh(now)
            item = self.manager.select(display, now, baseline, interacting)
            if item is None or interacting and item["urgency"] != "CRITICAL":
                return None
            return present(item, self.store.values[item["signal_id"]])

    def briefing(self) -> dict[str, Any]:
        with self.lock:
            now = self.clock()
            self._refresh(now)
            result = build(self.store.values, self.house.snapshot(now), self.activity,
                           now, self._source_sequence, self.config["signal_ttl"])
            from .targeting import SCENES, target

            display = self.manager.displays.get("kiosk")
            candidates = [i.snapshot() for i in self.manager.items.values()
                          if display and target(i, display, SCENES)[0] and i.expires_at > now]
            result["alerts"] = [i for i in candidates if i.get("urgency") in ("IMPORTANT", "ACTIONABLE", "CRITICAL")
                                and not i.get("suppression") and not i.get("acknowledged")]
            result["alerts"].sort(key=lambda i: (-{"CRITICAL": 3, "IMPORTANT": 2, "ACTIONABLE": 1}[i["urgency"]], -i["priority"]))
            return result

    def diagnostics(self) -> dict[str, Any]:
        with self.lock:
            now = self.clock()
            self._refresh(now)
            # Diagnostics do not select or mark an item as displayed.
            result = self.manager.snapshot(now)
            result.update(
                enabled=self.config["enabled"],
                context=self.house.snapshot(now),
                config=self.config,
                source_observed_at=self._source_sequence,
            )
            return result

    def action(self, item_id: str, action: str, seconds: float = 300) -> None:
        with self.lock:
            now = self.clock()
            self._refresh(now)
            self.manager.action(item_id, action, now, seconds)
            self._refresh(now)

    def display_state(self, display_id: str, changes: dict[str, Any]) -> None:
        with self.lock:
            display = self.manager.displays.get(display_id)
            if display is None:
                raise ValueError("unknown display")
            if not changes or set(changes) - {"available", "idle_state", "user_visible"}:
                raise ValueError("display state accepts available, idle_state, user_visible")
            if not all(isinstance(value, bool) for value in changes.values()):
                raise ValueError("display states must be boolean")
            for key, value in changes.items():
                setattr(display, key, value)
            self.history.record(self.clock(), "display", id=display_id, **changes)

    def family(self, display: str) -> str:
        with self.lock:
            value = self.manager.displays.get(display)
            return value.family if value else display

    def close(self) -> None:
        with self.lock:
            self.history.close()
