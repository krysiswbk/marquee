"""Deterministic household scenarios and policy mechanism regression tests."""

import copy
import json

import pytest

from cast.marquee.attention.history import History
from cast.marquee.attention.manager import AttentionManager
from cast.marquee.attention.schema import validate
from cast.marquee.attention.service import AttentionService
from cast.marquee.signals.model import Signal, SignalStore

NOW = 1_800_000_000.0


def rule(id="door", **changes):
    return {
        "id": id,
        "match": {"category": id},
        "title": id,
        "active_state": "on",
        "escalation": [
            {"id": "awareness", "after": 120, "priority": 30, "urgency": "ACTIONABLE"},
            {"id": "important", "after": 300, "priority": 60, "urgency": "IMPORTANT"},
            {"id": "persistent", "after": 900, "priority": 80, "urgency": "IMPORTANT"},
            {
                "id": "away",
                "priority": 90,
                "urgency": "CRITICAL",
                "when": {"field": "context.nobody_home", "op": "eq", "value": True},
            },
        ],
        **changes,
    }


def immediate(id, priority=30, urgency="ACTIONABLE", **changes):
    return rule(id, escalation=[{"id": "active", "priority": priority, "urgency": urgency}], **changes)


class House:
    def __init__(self, rules=None, **config):
        self.now = NOW
        self.context = {}
        self.store = SignalStore()
        self.history = History(limit=100)
        self.manager = AttentionManager(
            validate({"rules": rules or [rule()], **config}), self.store, self.history, self.now
        )
        self.media = {"id": "plex:now", "title": "A movie"}

    def state(self, entity="door1", state="on", category="door", **attrs):
        s = Signal(
            id=entity,
            type="binary_sensor",
            source="test",
            entity_id=entity,
            category=category,
            state=state,
            created_at=self.now,
            updated_at=self.now,
            active_since=self.now,
            expires_at=self.now + 10000,
            attributes=attrs,
        )
        self.store.observe(s, self.now)

    def step(self, seconds=0, display="kiosk", baseline=None):
        self.now += seconds
        self.manager.refresh(self.context, self.now)
        return self.manager.select(display, self.now, baseline)


# The twelve requested household scenarios.
def test_normal_door_open_close_never_interrupts():
    h = House()
    h.state()
    assert h.step() is None
    h.now += 5
    h.state(state="off")
    assert h.step(400) is None


def test_door_five_minutes_escalates():
    h = House()
    h.state()
    assert h.step(120)["stage"] == "awareness"
    assert h.step(180)["stage"] == "important"
    assert any(e["kind"] == "escalation" for e in h.history.read(h.now))


def test_door_away_is_immediately_critical():
    h = House()
    h.context["nobody_home"] = True
    h.state()
    assert h.step()["urgency"] == "CRITICAL"


def test_media_yields_to_door_and_returns():
    h = House()
    h.state()
    assert h.step(baseline=h.media) is None
    assert h.step(300, baseline=h.media)["rule_id"] == "door"
    h.now += 1
    h.state(state="off")
    assert h.step(baseline=h.media) is None
    assert h.manager.explanations["kiosk"]["winner"] == h.media


def test_radar_yields_to_weather_warning():
    h = House([immediate("radar", urgency="CONTEXTUAL"), immediate("warning", urgency="IMPORTANT")])
    h.state("radar", category="radar")
    assert h.step()["rule_id"] == "radar"
    h.state("warning", category="warning")
    # Important respects the current minimum duration, then takes over.
    assert h.step(15)["rule_id"] == "warning"


def test_leak_critical_preempts_noninterruptible_dwell_everywhere():
    h = House(
        [
            immediate("door", minimum_display_time=600),
            immediate("leak", urgency="CRITICAL", debounce=100, strategy="local"),
        ]
    )
    h.state()
    h.step()
    h.state("leak", category="leak", location="basement")
    for display in ("kiosk", "hubs", "garage"):
        assert h.step(display=display)["rule_id"] == "leak"


def test_leak_resolution_releases_immediately_and_restores_useful_content():
    h = House([immediate("door"), immediate("leak", urgency="CRITICAL", minimum_display_time=900)])
    h.state()
    h.step()
    h.state("leak", category="leak")
    assert h.step()["rule_id"] == "leak"
    h.now += 1
    h.state("leak", "off", category="leak")
    assert h.step()["rule_id"] == "door"
    assert any(e.get("state") == "RESOLVED" for e in h.history.read(h.now))


def test_flapping_does_not_accumulate_open_duration():
    h = House()
    for _ in range(30):
        h.state()
        assert h.step(5) is None
        h.state(state="off")
        assert h.step(5) is None
    assert not h.manager.items


def test_two_doors_group_and_one_closing_keeps_other():
    h = House([rule(grouping_key="doors")])
    h.state()
    h.state("door2")
    item = h.step(300)
    assert len(item["members"]) == 2
    h.now += 1
    h.state(state="off")
    assert len(h.step()["members"]) == 1


def test_sleep_context_changes_score():
    h = House(
        [
            immediate(
                "door",
                modifiers=[
                    {
                        "id": "sleeping",
                        "delta": 20,
                        "when": {"field": "context.sleeping", "op": "eq", "value": True},
                    }
                ],
            )
        ]
    )
    h.context["sleeping"] = True
    h.state()
    item = h.step()
    assert item["score"] == 50
    assert {"reason": "sleeping", "delta": 20} in item["components"]


def test_information_finishes_and_respects_cooldown_then_resurfaces():
    h = House(
        [
            immediate(
                "washer", persistence="timed", minimum_display_time=0, maximum_display_time=10, cooldown=300
            )
        ]
    )
    h.state("washer", category="washer")
    assert h.step()
    assert h.step(10) is None
    assert h.step(299) is None
    assert h.step(1)


def test_display_unavailable_releases_and_returns_when_available():
    h = House([immediate("door")])
    h.state()
    assert h.step()
    h.manager.displays["kiosk"].available = False
    assert h.step(baseline=h.media) is None
    assert h.manager.explanations["kiosk"]["winner"] is None
    h.manager.displays["kiosk"].available = True
    assert h.step()


def test_acknowledgement_is_episode_and_stage_scoped():
    h = House([rule(acknowledgement="suppress")])
    h.state()
    item = h.step(120)
    h.manager.action(item["id"], "acknowledge", h.now)
    assert h.step() is None
    assert h.step(180)["stage"] == "important"


def test_critical_acknowledgement_never_hides_active_leak():
    h = House([immediate("leak", urgency="CRITICAL", acknowledgement="suppress")])
    h.state("leak", category="leak")
    item = h.step()
    h.manager.action(item["id"], "acknowledge", h.now)
    assert h.step()["acknowledged"]
    with pytest.raises(ValueError):
        h.manager.action(item["id"], "suppress", h.now)


def test_minimum_dwell_and_switch_margin_prevent_thrashing():
    h = House([immediate("a", priority=30), immediate("b", priority=40)])
    h.state("a", category="a")
    assert h.step()["rule_id"] == "a"
    h.state("b", category="b")
    assert h.step(1)["rule_id"] == "a"
    assert h.step(14)["rule_id"] == "b"


def test_local_targeted_and_ambient_display_policies():
    for strategy, extras in [("local", {}), ("targeted", {"eligible_displays": ["garage"]})]:
        h = House([immediate("door", strategy=strategy, **extras)])
        h.state(location="garage")
        assert h.step(display="kiosk") is None
        assert h.step(display="garage")
    h = House([immediate("door", strategy="ambient")])
    h.state()
    h.manager.displays["kiosk"].idle_state = False
    assert h.step() is None


def test_capability_fallback():
    h = House([immediate("door", preferred_scene="radar")])
    h.state()
    h.manager.displays["kiosk"].supports_animation = False
    assert h.step()["renderer"] == "attention"


def test_expiry_releases_even_during_dwell():
    h = House([immediate("door", minimum_display_time=9999)])
    h.state()
    h.store.values["door1"].expires_at = h.now + 2
    assert h.step()
    assert h.step(2) is None
    assert any(e.get("state") == "EXPIRED" for e in h.history.read(h.now))


def test_dedupe_does_not_sum_scores():
    h = House([immediate("door", dedupe_key="one")])
    h.state()
    h.state("door2")
    item = h.step()
    assert item["score"] == 30
    assert len(item["members"]) == 2


def test_unknown_context_cannot_mean_away():
    h = House()
    h.context["nobody_home"] = None
    h.state()
    assert h.step() is None


def test_continuous_heartbeat_preserves_duration_out_of_order_rejected():
    h = House()
    h.state()
    h.now += 100
    h.state()
    assert h.store.values["door1"].active_since == NOW
    old = copy.deepcopy(h.store.values["door1"])
    old.updated_at -= 10
    old.state = "off"
    assert not h.store.observe(old, h.now)
    assert h.store.values["door1"].state == "on"


def test_history_is_bounded_by_count_and_age():
    history = History(limit=10, retention=60)
    for i in range(30):
        history.record(NOW + i, "test", id=str(i))
    assert len(history.read(NOW + 30)) == 10
    assert history.read(NOW + 100) == []


@pytest.mark.parametrize(
    "change",
    [
        {"unexpected": True},
        {"signal_ttl": float("nan")},
        {"max_signals": 2.5},
        {"displays": [{"id": "a"}, {"id": "a"}]},
        {"rules": [rule(escalation=[])]},
        {"rules": [rule(strategy="targeted")]},
        {"rules": [rule(preferred_scene="missing")]},
        {"rules": [rule(cooldown=-1)]},
        {"rules": [rule(persistence="timed")]},
        {"rules": [rule(eligible_displays=["missing"])]},
        {
            "rules": [
                rule(
                    modifiers=[{"id": "x", "delta": 10, "when": {"field": "evil.x", "op": "eq", "value": 1}}]
                )
            ]
        },
        {"rules": [rule(escalation=[{"id": "x", "urgency": "PANIC"}])]},
        {"context_bindings": {"home": {"entity_id": "x", "values": []}}},
    ],
)
def test_configuration_rejects_invalid_policy(change):
    with pytest.raises(ValueError):
        validate(change)


def test_service_full_snapshot_stale_cleanup_and_context(tmp_path):
    now = [NOW]
    service = AttentionService(
        {
            "attention": {
                "rules": [immediate("door")],
                "signal_bindings": [{"entity_id": "binary_sensor.door", "category": "door"}],
                "context_bindings": {
                    "home": {"entity_id": "binary_sensor.occupied", "values": {"on": True, "off": False}}
                },
            }
        },
        str(tmp_path),
        lambda: now[0],
    )
    service.ingest(
        {
            "states": [
                {"entity_id": "binary_sensor.door", "state": "on"},
                {"entity_id": "binary_sensor.occupied", "state": "off"},
            ],
            "full": True,
        }
    )
    assert service.choose("kiosk", None)
    assert service.diagnostics()["context"]["nobody_home"]
    now[0] += 1
    service.ingest({"states": [], "full": True})
    assert service.choose("kiosk", None) is None
    assert service.diagnostics()["context"]["home"] is None
    service.close()


def test_default_weather_alert_preempts_media_and_clears(tmp_path):
    now = [NOW]
    service = AttentionService({}, str(tmp_path), lambda: now[0])
    warning = {
        "id": "weather:alert:1",
        "type": "weather",
        "source": "weather",
        "subtype": "alert",
        "title": "Severe thunderstorm warning",
    }
    service.sync_contexts([warning], {"title": "Movie"})
    payload = service.choose("hubs", {"id": "plex:now"})
    assert payload["title"] == warning["title"]
    now[0] += 1
    service.sync_contexts([], {"title": "Movie"})
    assert service.choose("hubs", {"id": "plex:now"}) is None
    service.close()


def test_diagnostics_reads_do_not_start_display_timers(tmp_path):
    now = [NOW]
    service = AttentionService(
        {
            "attention": {
                "rules": [immediate("door")],
                "signal_bindings": [{"entity_id": "binary_sensor.door", "category": "door"}],
            }
        },
        str(tmp_path),
        lambda: now[0],
    )
    service.ingest({"states": [{"entity_id": "binary_sensor.door", "state": "on"}]})
    service.diagnostics()
    service.diagnostics()
    assert not any(e["kind"] == "winner" for e in service.history.read(NOW))
    assert next(iter(service.manager.controls.values())).get("shown_at") is None
    service.close()


def test_all_examples_validate():
    from pathlib import Path

    path = Path(__file__).parents[1] / "docs" / "attention.example.json"
    if path.exists():
        validate(json.loads(path.read_text()))


def test_flap_after_display_obeys_cooldown_but_away_escalation_bypasses():
    h = House([rule()])
    h.state()
    assert h.step(300)
    h.now += 1
    h.state(state="off")
    assert h.step() is None
    h.now += 1
    h.state()
    assert h.step(120) is None
    h.context["nobody_home"] = True
    assert h.step()["urgency"] == "CRITICAL"


def test_display_context_modifier_and_deterministic_tie():
    h = House(
        [
            immediate(
                "a",
                strategy="targeted",
                eligible_displays=["kiosk", "garage"],
                modifiers=[
                    {
                        "id": "nearby",
                        "delta": 20,
                        "when": {"field": "display.location", "op": "eq", "value": "garage"},
                    }
                ],
            ),
            immediate("b", priority=40),
        ]
    )
    h.state("a", category="a")
    h.state("b", category="b")
    assert h.step(display="kiosk")["rule_id"] == "b"
    assert h.step(display="garage")["rule_id"] == "a"


def test_explicit_suppression_resolves_and_does_not_apply_to_new_episode():
    h = House([immediate("door", cooldown=0)])
    h.state()
    item = h.step()
    h.manager.action(item["id"], "suppress", h.now, 300)
    assert h.step() is None
    h.now += 1
    h.state(state="off")
    h.step()
    h.now += 1
    h.state()
    assert h.step()


def test_unavailable_sensor_health_is_aggregated_and_throttled(tmp_path):
    now = [NOW]
    service = AttentionService(
        {
            "attention": {
                "signal_ttl": 1000,
                "signal_bindings": [{"entity_id": "binary_sensor.a"}, {"entity_id": "binary_sensor.b"}],
                "rules": [
                    immediate(
                        "sensor_health",
                        active_state="unavailable",
                        debounce=120,
                        grouping_key="health",
                        persistence="timed",
                        minimum_display_time=0,
                        maximum_display_time=10,
                        cooldown=3600,
                    )
                ],
            }
        },
        str(tmp_path),
        lambda: now[0],
    )
    service.ingest(
        {
            "states": [
                {"entity_id": entity, "state": "unavailable"}
                for entity in ("binary_sensor.a", "binary_sensor.b")
            ]
        }
    )
    assert service.choose("kiosk", None) is None
    now[0] += 120
    payload = service.choose("kiosk", None)
    assert len(payload["attention"]["members"]) == 2
    now[0] += 10
    assert service.choose("kiosk", None) is None
    service.close()


def test_cooldown_survives_restart_but_stale_conditions_do_not(tmp_path):
    now = [NOW]
    config = {
        "attention": {
            "rules": [
                immediate("door", persistence="timed", minimum_display_time=0, maximum_display_time=10)
            ],
            "signal_bindings": [{"entity_id": "binary_sensor.door", "category": "door"}],
        }
    }
    service = AttentionService(config, str(tmp_path), lambda: now[0])
    body = {"states": [{"entity_id": "binary_sensor.door", "state": "on"}]}
    service.ingest(body)
    assert service.choose("kiosk", None)
    now[0] += 10
    assert service.choose("kiosk", None) is None
    service.close()
    service = AttentionService(config, str(tmp_path), lambda: now[0])
    assert service.choose("kiosk", None) is None
    service.ingest(body)
    assert service.choose("kiosk", None) is None
    service.close()


def test_interaction_suppresses_without_counting_appearance(tmp_path):
    service = AttentionService(
        {
            "attention": {
                "rules": [immediate("door")],
                "signal_bindings": [{"entity_id": "binary_sensor.door", "category": "door"}],
            }
        },
        str(tmp_path),
        lambda: NOW,
    )
    service.ingest({"states": [{"entity_id": "binary_sensor.door", "state": "on"}]})
    assert service.choose("kiosk", None, interacting=True) is None
    assert next(iter(service.manager.controls.values())).get("shown_at") is None
    service.close()


def test_worsening_modifier_survives_repeated_read_evaluations():
    h = House(
        [
            rule(
                modifiers=[
                    {
                        "id": "worsening",
                        "delta": 25,
                        "when": {"field": "item.worsening", "op": "eq", "value": True},
                    }
                ]
            )
        ]
    )
    h.state()
    h.step(120)
    h.step(180)
    item = h.step()
    assert {"reason": "worsening", "delta": 25} in item["components"]


def test_critical_has_universal_fallback_on_text_only_display():
    h = House([immediate("leak", urgency="CRITICAL", preferred_scene="radar", fallback_scene="image")])
    h.state("leak", category="leak")
    h.manager.displays["kiosk"].supports_image = False
    assert h.step()["renderer"] == "attention"


def test_stale_and_malformed_snapshots_are_atomic(tmp_path):
    now = [NOW]
    config = {"attention": {"signal_bindings": [{"entity_id": "binary_sensor.door"}]}}
    service = AttentionService(config, str(tmp_path), lambda: now[0])
    body = {"states": [{"entity_id": "binary_sensor.door", "state": "on"}], "observed_at": NOW}
    service.ingest(body)
    now[0] += 1
    with pytest.raises(ValueError):
        service.ingest(body)
    with pytest.raises(ValueError):
        service.ingest(
            {
                "states": [
                    {"entity_id": "binary_sensor.door", "state": "off"},
                    {"entity_id": "bad", "state": 42},
                ]
            }
        )
    assert service.store.values["ha:binary_sensor.door"].state == "on"
    service.close()


def test_schema_rejects_display_dependent_escalation():
    with pytest.raises(ValueError):
        validate(
            {
                "rules": [
                    rule(
                        "door",
                        escalation=[
                            {
                                "id": "bad",
                                "when": {"field": "display.location", "op": "eq", "value": "garage"},
                            }
                        ],
                    )
                ]
            }
        )


def test_signal_capacity_removes_only_expired_observations():
    h = House()
    h.store.limit = 1
    h.state()
    with pytest.raises(ValueError):
        h.state("door2")
    h.store.values["door1"].expires_at = h.now
    h.state("door2")
    assert set(h.store.values) == {"door2"}


def test_composition_critical_bypasses_freeze_and_interaction_then_restores_media(tmp_path, monkeypatch):
    from cast.marquee import composition as app
    from cast.marquee.core.arbitration import ContextArbiter

    now = [NOW]
    service = AttentionService(
        {
            "attention": {
                "rules": [immediate("leak", urgency="CRITICAL")],
                "signal_bindings": [{"entity_id": "binary_sensor.leak", "category": "leak"}],
            }
        },
        str(tmp_path),
        lambda: now[0],
    )
    monkeypatch.setattr(app, "ATTENTION", {"value": service})
    monkeypatch.setattr(app, "ARBITER", ContextArbiter())
    monkeypatch.setattr(app, "PROVIDER_ENGINE", {"value": None})
    monkeypatch.setattr(app, "saved_contexts", lambda: [])
    monkeypatch.setattr(app, "kiosk_interacting", lambda: False)
    media = {"playing": True, "title": "Movie"}
    assert app.best_context(media, "kiosk") == media
    app.ARBITER.control("freeze")
    service.ingest({"states": [{"entity_id": "binary_sensor.leak", "state": "on"}]})
    monkeypatch.setattr(app, "kiosk_interacting", lambda: True)
    assert app.best_context(media, "kiosk")["attention"]["urgency"] == "CRITICAL"
    now[0] += 1
    service.ingest({"states": [{"entity_id": "binary_sensor.leak", "state": "off"}]})
    monkeypatch.setattr(app, "kiosk_interacting", lambda: False)
    assert app.best_context(media, "kiosk") == media
    assert app.ARBITER.control_state()["frozen"]
    service.close()
