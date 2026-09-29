"""Deterministic attention lifecycle and arbitration. No source or renderer I/O."""

import copy
from dataclasses import asdict
from typing import Any

from ..signals.model import SignalStore
from .history import History
from .models import TIERS, AttentionItem, Display, Lifecycle
from .scoring import accepts, score, stage_for
from .targeting import SCENES, target


class AttentionManager:
    def __init__(self, config: dict[str, Any], store: SignalStore, history: History, now: float) -> None:
        self.config, self.store, self.history = config, store, history
        self.displays = {d["id"]: Display(**d) for d in config["displays"]}
        self.items: dict[str, AttentionItem] = {}
        self.controls = history.controls(now)
        self.selections: dict[str, dict[str, Any]] = {}
        self.explanations: dict[str, dict[str, Any]] = {}
        self.environments: dict[str, dict[str, Any]] = {}
        self.rules = {rule["id"]: rule for rule in config["rules"]}
        self._decisions: dict[tuple[str, str], str] = {}

    def _transition(self, item: AttentionItem, state: Lifecycle, now: float, reason: str) -> None:
        previous = self.items.get(item.id)
        if previous is None or previous.lifecycle != state or previous.stage != item.stage:
            self.history.record(
                now,
                "transition",
                id=item.id,
                previous=previous.lifecycle if previous else None,
                state=state,
                stage=item.stage,
                reason=reason,
            )
        item.lifecycle = state

    def refresh(self, context: dict[str, Any], now: float) -> None:
        next_items: dict[str, AttentionItem] = {}
        self.environments = {}
        active_count = sum(
            s.expires_at > now
            and any(accepts(rule, s) and s.state == rule["active_state"] for rule in self.rules.values())
            for s in self.store.values.values()
        )
        for rule in self.rules.values():
            for signal in self.store.values.values():
                if not accepts(rule, signal):
                    continue
                key = f"{rule['id']}:{signal.id}"
                if (
                    signal.expires_at <= now
                    or signal.state != rule["active_state"]
                    or ("resolution_state" in rule and signal.state == rule["resolution_state"])
                ):
                    continue
                env = {
                    "signal": signal.snapshot(now),
                    "context": context,
                    "competition": {"active_signals": active_count},
                    "item": {},
                }
                stage, rank = stage_for(rule, env)
                if stage is None:
                    continue
                control = self.controls.setdefault(key, {})
                previous = self.items.get(key)
                if control.get("episode") != signal.active_since:
                    control.update(
                        episode=signal.active_since,
                        acknowledged_stage=None,
                        shown_at=None,
                        suppressed_until=0,
                        escalated_at=-1e30,
                    )
                # Escalation compares severity, not declaration order.
                escalated = bool(
                    previous
                    and (TIERS[stage["urgency"]], stage["priority"])
                    > (TIERS[previous.urgency], previous.priority)
                )
                if escalated and previous is not None:
                    control.update(
                        acknowledged_stage=None, cooldown_until=0, shown_at=None, suppressed_until=0
                    )
                    control["escalated_at"] = now
                    self.history.record(now, "escalation", id=key, previous=previous.stage, stage=stage["id"])
                acknowledged = control.get("acknowledged_stage") == stage["id"]
                future = [
                    signal.active_since + s["after"]
                    for s in rule["escalation"]
                    if signal.active_since + s["after"] > now
                ]
                item = AttentionItem(
                    id=key,
                    signal_id=signal.id,
                    rule_id=rule["id"],
                    title=rule["title"],
                    summary=rule["summary"],
                    priority=stage["priority"],
                    urgency=stage["urgency"],
                    persistence=stage.get("persistence", rule["persistence"]),
                    interruptibility=rule["interruptibility"],
                    minimum_display_time=rule["minimum_display_time"],
                    maximum_display_time=rule["maximum_display_time"],
                    cooldown=rule["cooldown"],
                    acknowledgement_required=rule["acknowledgement_required"],
                    eligible_displays=rule["eligible_displays"],
                    preferred_scene=rule["preferred_scene"],
                    fallback_scene=rule["fallback_scene"],
                    dedupe_key=rule["dedupe_key"] or f"{rule['id']}:{signal.dedupe_key or signal.id}",
                    grouping_key=rule["grouping_key"],
                    strategy=rule["strategy"],
                    location=str(signal.attributes.get("location", "")),
                    stage=stage["id"],
                    stage_rank=rank,
                    episode=signal.active_since,
                    expires_at=signal.expires_at,
                    next_escalation_at=min(future) if future else None,
                    acknowledged=acknowledged,
                    members=[key],
                )
                critical = item.urgency == "CRITICAL" or item.strategy == "critical"
                if critical:
                    item.urgency = "CRITICAL"
                shown_at = control.get("shown_at")
                if (
                    not critical
                    and item.persistence == "timed"
                    and shown_at is not None
                    and now >= shown_at + item.maximum_display_time
                ):
                    control.update(shown_at=None, cooldown_until=now + item.cooldown)
                    self.history.save_control(key, now + max(item.cooldown, 1), control)
                suppression = ""
                available_at = None
                if not critical:
                    if now - signal.active_since < rule["debounce"]:
                        suppression = "activation debounce"
                        available_at = signal.active_since + rule["debounce"]
                    elif control.get("cooldown_until", 0) > now:
                        suppression = "cooldown"
                        available_at = control["cooldown_until"]
                    elif control.get("suppressed_until", 0) > now:
                        suppression = "explicit suppression"
                        available_at = control["suppressed_until"]
                    elif acknowledged and rule["acknowledgement"] == "suppress":
                        suppression = "acknowledged"
                item.suppression = suppression
                item.available_at = available_at
                env["item"] = {
                    "acknowledged": acknowledged,
                    "recently_displayed": control.get("last_shown", -1e30) + item.cooldown > now,
                    "worsening": now - control.get("escalated_at", -1e30) < rule["worsening_seconds"],
                }
                item.score, item.components = score(
                    rule, stage, env, acknowledged, env["item"]["recently_displayed"]
                )
                state = (
                    Lifecycle.SUPPRESSED
                    if suppression
                    else Lifecycle.ACKNOWLEDGED
                    if acknowledged
                    else Lifecycle.ESCALATED
                    if escalated
                    else Lifecycle.ACTIVE
                )
                if previous is None:
                    self._transition(item, Lifecycle.NEW, now, "condition became eligible")
                self._transition(item, state, now, suppression or "policy evaluation")
                next_items[key] = item
                self.environments[key] = env
        for key, previous in self.items.items():
            if key in next_items:
                continue
            previous_signal = self.store.values.get(previous.signal_id)
            state = (
                Lifecycle.EXPIRED
                if not previous_signal or previous_signal.expires_at <= now
                else Lifecycle.RESOLVED
            )
            self._transition(
                previous,
                state,
                now,
                "source expired" if state == Lifecycle.EXPIRED else "condition no longer eligible",
            )
            control = self.controls[key]
            if control.get("last_shown") is not None:
                control["cooldown_until"] = max(control.get("cooldown_until", 0), now + previous.cooldown)
                self.history.save_control(key, now + max(previous.cooldown, 1), control)
        self.items = next_items
        for key in list(self.controls):
            control = self.controls[key]
            if (
                key not in next_items
                and max(control.get("cooldown_until", 0), control.get("suppressed_until", 0)) <= now
            ):
                del self.controls[key]
        self._decisions = {key: value for key, value in self._decisions.items() if key[1] in next_items}
        self.store.prune(now, self.config["history_seconds"])

    def select(
        self, display_id: str, now: float, baseline: dict[str, Any] | None = None, interacting: bool = False
    ) -> dict[str, Any] | None:
        display = self.displays.get(display_id)
        if display is None:
            return None
        if interacting:
            baseline = None
        candidates: list[AttentionItem] = []
        rows: list[dict[str, Any]] = []
        scene_by_id: dict[str, str] = {}
        for original in self.items.values():
            item = copy.deepcopy(original)
            scene, reason = target(item, display, SCENES)
            env = {**self.environments[item.id], "display": asdict(display)}
            rule = self.rules[item.rule_id]
            stage = next(s for s in rule["escalation"] if s["id"] == item.stage)
            item.score, item.components = score(
                rule, stage, env, item.acknowledged, env["item"]["recently_displayed"]
            )
            suppression = item.suppression or (reason if scene is None else "")
            if interacting and item.urgency != "CRITICAL":
                suppression = "user interacting"
            rows.append(
                {**item.snapshot(), "suppression": suppression, "renderer": scene, "target_reason": reason}
            )
            if suppression:
                decision_key = (display_id, item.id)
                if self._decisions.get(decision_key) != suppression:
                    self.history.record(
                        now, "suppression", id=item.id, display=display_id, reason=suppression
                    )
                    self._decisions[decision_key] = suppression
            else:
                self._decisions.pop((display_id, item.id), None)
                candidates.append(item)
                scene_by_id[item.id] = str(scene)
        candidates.sort(key=lambda item: (-TIERS[item.urgency], -item.score, item.id))
        unique: dict[str, AttentionItem] = {}
        for item in candidates:
            key = item.grouping_key or item.dedupe_key
            if key in unique:
                unique[key].members.extend(item.members)
                for row in rows:
                    if row["id"] == item.id:
                        row["suppression"] = f"grouped with {unique[key].id}"
            else:
                unique[key] = item
        candidates = list(unique.values())
        winner = candidates[0] if candidates else None
        previous = self.selections.get(display_id)
        reason = "highest tier and contextual score" if winner else "ambient compatibility policy"
        # The baseline is the established rotating/manual ambient strategy.
        if winner and winner.urgency == "AMBIENT" and baseline and winner.score <= 0:
            winner = None
            reason = "ambient candidate has no positive attention value"
        if previous and winner and winner.id != previous["id"] and winner.urgency != "CRITICAL":
            prior = next((item for item in candidates if item.id == previous["id"]), None)
            if prior and (
                now < previous["since"] + prior.minimum_display_time
                or (not prior.interruptibility and prior.persistence == "timed")
                or (
                    TIERS[winner.urgency] == TIERS[prior.urgency]
                    and winner.score < prior.score + self.config["switch_margin"]
                )
            ):
                winner = prior
                reason = "current item dwell / interruptibility / switch margin"
        selected_id = winner.id if winner else baseline.get("id") if baseline else None
        if (
            not display.available
            or not display.user_visible
            and not (winner and winner.urgency == "CRITICAL")
        ):
            winner, selected_id = None, None
            baseline = None
            reason = "display unavailable or not visible"
        if not previous or previous["id"] != selected_id:
            self.history.record(
                now,
                "winner",
                display=display_id,
                previous=previous["id"] if previous else None,
                id=selected_id,
                reason=reason,
            )
            self.selections[display_id] = {"id": selected_id, "since": now}
        if winner:
            for member in winner.members:
                control = self.controls[member]
                if control.get("shown_at") is None:
                    control["shown_at"] = now
                control["last_shown"] = now
            result = winner.snapshot()
            result["renderer"] = scene_by_id[winner.id]
            result["members"] = winner.members
            if winner.grouping_key and len(winner.members) > 1:
                result["title"] = f"{winner.title} ({len(winner.members)})"
            control = self.controls[winner.id]
            result["display_until"] = (
                min(winner.expires_at, control["shown_at"] + winner.maximum_display_time)
                if winner.persistence == "timed" and winner.urgency != "CRITICAL"
                else winner.expires_at
            )
        else:
            result = None
        self.explanations[display_id] = {
            "display": asdict(display),
            "winner": result or baseline,
            "reason": reason,
            "candidates": rows,
            "ambient": {
                "id": baseline.get("id"),
                "policy": "existing rotation/manual/UFC and Cast eligibility",
                "urgency": "AMBIENT",
            }
            if baseline
            else None,
            "evaluated_at": now,
        }
        return result

    def action(self, item_id: str, action: str, now: float, seconds: float = 300) -> None:
        item = self.items.get(item_id)
        if item is None:
            raise ValueError("attention item no longer active")
        if action not in ("acknowledge", "suppress"):
            raise ValueError("unsupported attention action")
        if action == "suppress" and (item.urgency == "CRITICAL" or item.strategy == "critical"):
            raise ValueError("critical conditions cannot be manually suppressed")
        # Group acknowledgement covers currently active members, never future events.
        members = [
            value
            for value in self.items.values()
            if value.id == item_id or (item.grouping_key and value.grouping_key == item.grouping_key)
        ]
        for member in members:
            if action == "suppress" and member.urgency == "CRITICAL":
                continue
            control = self.controls[member.id]
            if action == "acknowledge":
                control["acknowledged_stage"] = member.stage
            else:
                control["suppressed_until"] = now + seconds
            self.history.record(now, action, id=member.id, stage=member.stage)

    def snapshot(self, now: float) -> dict[str, Any]:
        items = []
        for item in self.items.values():
            snapshot = item.snapshot()
            signal = self.store.values.get(item.signal_id)
            if signal:
                friendly_name = str(signal.attributes.get("friendly_name", "")).strip()
                location = str(signal.attributes.get("location", "")).strip()
                identity = {}
                if friendly_name:
                    identity["label"] = friendly_name
                if location:
                    identity["location"] = location
                if identity:
                    snapshot["identity"] = identity
            items.append(snapshot)
        return {
            "signals": [s.snapshot(now) for s in self.store.values.values()],
            "items": items,
            "displays": copy.deepcopy(self.explanations),
            "history": self.history.read(now),
        }
