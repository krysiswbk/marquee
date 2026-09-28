from pathlib import Path

from cast.marquee.attention.schema import FORM_SCHEMA
from cast.marquee.attention.service import AttentionService

ROOT = Path(__file__).parents[1]


def test_attention_form_ranges_are_schema_backed() -> None:
    assert FORM_SCHEMA["signal_ttl"] == {
        "min": 5, "max": 86400, "step": 1, "unit": "seconds", "required": True
    }
    assert FORM_SCHEMA["quiet_hours"]["min"] == 0
    assert FORM_SCHEMA["quiet_hours"]["max"] == 23
    assert FORM_SCHEMA["history_limit"]["max"] == 50000
    assert FORM_SCHEMA["modifier_delta"]["min"] == -1000


def test_attention_editor_uses_semantic_numeric_controls_and_inline_validation() -> None:
    source = (ROOT / "output" / "attention-settings.js").read_text()
    for token in ("state.schema", "required", "aria-invalid", "aria-describedby", "attention-${id}",
                  "name: `attention.${id}`", "signal_ttl", "quiet_hours", "modifier_delta"):
        assert token in source
    assert "Fix each invalid field or JSON condition before saving." in source


def test_attention_savebar_has_tablet_focus_clearance() -> None:
    styles = (ROOT / "output" / "settings-admin.css").read_text()
    assert "padding:30px 24px calc(136px + env(safe-area-inset-bottom))" in styles
    assert "scroll-margin-bottom:calc(112px + env(safe-area-inset-bottom))" in styles


def test_screen_samples_are_independent_of_cast_discovery() -> None:
    source = (ROOT / "output" / "display-tests.js").read_text()
    assert "screens = await request('/api/screen-test')" in source
    assert "request('/devices').then(renderDevices)" in source
    assert "Promise.all" not in source
    assert "Live / Kiosk tests remain available." in source
    assert "Wait for a Cast display, or choose Live / Kiosk." in source


def test_active_attention_items_expose_authoritative_human_identity(tmp_path) -> None:
    service = AttentionService({"attention": {
        "signal_bindings": [
            {"entity_id": "sensor.nursery_a", "category": "sensor_health", "location": "nursery"},
            {"entity_id": "sensor.nursery_b", "category": "sensor_health", "location": "nursery"},
        ],
        "rules": [{"id": "offline", "match": {"category": "sensor_health"},
                   "title": "Nursery device offline", "active_state": "unavailable",
                   "escalation": [{"id": "active", "after": 0, "priority": 20,
                                   "urgency": "ACTIONABLE"}]}]}}, str(tmp_path))
    service.ingest({"full": True, "states": [
        {"entity_id": "sensor.nursery_a", "state": "unavailable",
         "attributes": {"friendly_name": "Nursery monitor"}},
        {"entity_id": "sensor.nursery_b", "state": "unavailable",
         "attributes": {"friendly_name": "Nursery camera"}},
    ]})
    items = service.diagnostics()["items"]
    assert {item["identity"]["label"] for item in items} == {"Nursery monitor", "Nursery camera"}
    assert all(item["identity"]["location"] == "nursery" for item in items)
    assert all("entity_id" not in item["identity"] for item in items)
    service.close()
