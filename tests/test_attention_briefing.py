"""Activity must come from actual transitions, with honest freshness and scene selection."""
from datetime import datetime, timedelta, timezone
from typing import Any

from cast.marquee.attention.service import AttentionService


def service_at(tmp_path: Any) -> tuple[AttentionService, list[float]]:
    now = [1_800_000_000.0]
    service = AttentionService({"attention": {"signal_ttl": 90, "signal_bindings": [
        {"entity_id": "lock.front", "category": "door_lock", "location": "entrance"},
        {"entity_id": "binary_sensor.balcony", "category": "exterior_door"}],
        "rules": [{"id": "open_door", "match": {"category": "exterior_door"},
                   "title": "Door open", "active_state": "on", "acknowledgement_required": True,
                   "escalation": [{"id": "open", "after": 10, "urgency": "IMPORTANT", "priority": 60}]}]}},
        str(tmp_path), lambda: now[0])
    return service, now


def publish(service: AttentionService, lock: str = "locked", door: str = "off") -> None:
    service.ingest({"full": True, "states": [
        {"entity_id": "lock.front", "state": lock},
        {"entity_id": "binary_sensor.balcony", "state": door, "attributes": {"friendly_name": "Balcony door"}}]})


def test_startup_and_reconnect_do_not_invent_unlock(tmp_path: Any) -> None:
    service, now = service_at(tmp_path)
    publish(service, "unlocked")
    assert service.briefing()["events"] == []
    now[0] += 91
    publish(service, "locked")
    assert service.briefing()["events"] == []
    service.close()


def test_real_unlock_refresh_close_and_activity_expiry(tmp_path: Any) -> None:
    service, now = service_at(tmp_path)
    publish(service)
    now[0] += 1
    publish(service, "unlocked", "on")
    snapshot = service.briefing()
    assert len(snapshot["events"]) == 2
    assert any(e["title"] == "Front door lock unlocked" for e in snapshot["events"])
    assert len(snapshot["openings"]) == 2
    now[0] += 20
    publish(service, "unlocked", "on")
    assert len(service.briefing()["events"]) == 2
    assert service.briefing()["openings"][0]["duration"] == 20
    now[0] += 1
    publish(service)
    assert not service.briefing()["openings"]
    assert any(e["title"] == "Balcony door closed" for e in service.briefing()["events"])
    now[0] += 901
    publish(service)
    assert not service.briefing()["events"]
    service.close()


def test_stale_feed_never_claims_current_openings_or_replays_activity(tmp_path: Any) -> None:
    service, now = service_at(tmp_path)
    publish(service)
    now[0] += 1
    publish(service, "unlocked")
    now[0] += 91
    snapshot = service.briefing()
    assert not snapshot["fresh"] and not snapshot["openings"] and not snapshot["events"]
    assert "Front door lock" in snapshot["unknown"]
    service.close()


def test_briefing_alert_resolves_without_another_display_selection(tmp_path: Any) -> None:
    service, now = service_at(tmp_path)
    publish(service, door="on")
    now[0] += 11
    publish(service, door="on")
    alerts = service.briefing()["alerts"]
    assert len(alerts) == 1
    assert not any(e["kind"] == "winner" for e in service.history.read(now[0]))
    service.action(alerts[0]["id"], "acknowledge")
    assert not service.briefing()["alerts"]
    assert service.briefing()["openings"]
    now[0] += 1
    publish(service)
    assert not service.briefing()["alerts"] and not service.briefing()["openings"]
    service.close()


def test_routine_contexts_leave_live_scene_rotation_but_keep_briefing(tmp_path: Any, monkeypatch: Any) -> None:
    from cast.marquee import composition as app
    from cast.marquee.core.arbitration import ContextArbiter
    service, now = service_at(tmp_path)
    # Context dates follow wall clock because the legacy arbiter owns its clock.
    expiry = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    cards = [{"id": "calendar:1", "type": "calendar_event", "title": "Birthday", "expires": expiry,
              "priority": 30, "targets": ["kiosk"]},
             {"id": "gaming:1", "type": "gaming", "title": "Release", "expires": expiry, "priority": 40}]
    monkeypatch.setattr(app, "saved_contexts", lambda: cards)
    monkeypatch.setattr(app, "PROVIDER_ENGINE", {"value": None})
    monkeypatch.setattr(app, "ATTENTION", {"value": service})
    monkeypatch.setattr(app, "ARBITER", ContextArbiter())
    monkeypatch.setattr(app, "kiosk_interacting", lambda: False)
    assert app.best_context(None, "kiosk") is None
    assert app.ARBITER.control_state()["count"] == 0
    media = {"playing": True, "title": "Movie"}
    assert app.best_context(media, "kiosk") == media
    # Test clock is later than the fixture's expiry; sync with a matching expiry for briefing.
    future = datetime.fromtimestamp(now[0]+600, timezone.utc).isoformat()
    service.sync_contexts([{**c, "expires": future} for c in cards], None)
    assert len(service.briefing()["cards"]) == 2
    service.close()


def test_important_house_event_brings_desk_forward_critical_keeps_takeover(tmp_path: Any, monkeypatch: Any) -> None:
    from cast.marquee import composition as app
    from cast.marquee.core.arbitration import ContextArbiter
    service, now = service_at(tmp_path)
    monkeypatch.setattr(app, "saved_contexts", lambda: [])
    monkeypatch.setattr(app, "PROVIDER_ENGINE", {"value": None})
    monkeypatch.setattr(app, "ATTENTION", {"value": service})
    monkeypatch.setattr(app, "ARBITER", ContextArbiter())
    monkeypatch.setattr(app, "kiosk_interacting", lambda: False)
    publish(service, door="on")
    now[0] += 11
    publish(service, door="on")
    payload = app.best_context({"playing": True, "title": "Movie"}, "kiosk")
    assert payload and not payload["playing"] and payload["householdFocus"]
    assert app.best_context(None, "hubs")["attention"]["urgency"] == "IMPORTANT"
    now[0] += 1
    publish(service)
    assert app.best_context({"playing": True, "title": "Movie"}, "kiosk")["title"] == "Movie"
    service.close()


def test_nursery_offline_warning_is_debounced_resolves_and_expires(tmp_path: Any) -> None:
    now = [1_800_000_000.0]
    entity = 'binary_sensor.nursery_motion_sensor_motion'
    service = AttentionService({'attention': {'signal_ttl': 90, 'signal_bindings': [
        {'entity_id': entity, 'category': 'maintenance', 'location': 'nursery'}]}},
        str(tmp_path), lambda: now[0])
    def send(state: str) -> None:
        service.ingest({'full': True, 'states': [{'entity_id': entity, 'state': state,
            'attributes': {'friendly_name': 'Nursery motion'}}]})
    send('unavailable')
    assert service.briefing()['device_health'] == []
    now[0] += 61
    send('unavailable')
    assert service.briefing()['device_health'][0]['name'] == 'Nursery motion'
    assert service.briefing()['alerts'] == []  # Advisory does not take over playback.
    now[0] += 1
    send('off')
    assert service.briefing()['device_health'] == []  # Off is a working motion sensor.
    now[0] += 1
    send('unknown')
    now[0] += 61
    send('unknown')
    assert service.briefing()['device_health']
    now[0] += 91
    assert not service.briefing()['fresh']
    assert service.briefing()['device_health'] == []
    service.close()
