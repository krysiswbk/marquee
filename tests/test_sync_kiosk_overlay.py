"""The HA launcher must leave Browser Mod's popup before showing Marquee."""

import json
import runpy
import sys
from pathlib import Path


def test_launcher_redirects_to_persistent_wrapper_and_avoids_reopen():
    integration = Path(__file__).parents[1] / "integrations/homeassistant"
    sys.path.insert(0, str(integration))
    try:
        plan = runpy.run_path(str(integration / "sync_kiosk_overlay.py"))["plan"]
    finally:
        sys.path.pop(0)
    current = {
        "id": "kiosk_marquee_plex_overlay",
        "triggers": [
            {"id": "manual_launch", "trigger": "state", "entity_id": "input_button.marquee_show_kiosk_overlay"},
            {"id": "kiosk_idle", "trigger": "state", "entity_id": "binary_sensor.sb2_kiosk"},
            {"id": "plex_playing", "trigger": "state", "entity_id": "media_player.shield_2"},
        ],
        "actions": [{"choose": [{"conditions": [{"condition": "template", "value_template": "{{ true }}"}], "sequence": [
            {"action": "browser_mod.refresh", "data": {"browser_id": ["kiosk"]}},
            {"delay": "00:00:08"},
            {"action": "browser_mod.popup", "data": {"tag": "marquee", "content": {
                "type": "iframe", "aspect_ratio": "62%", "url": "http://marquee/kiosk"
            }}},
        ]}]}],
    }
    original = json.dumps(current, sort_keys=True)
    updated = plan(current)
    sequence = updated["actions"][0]["choose"][0]["sequence"]
    assert json.dumps(current, sort_keys=True) == original
    assert [trigger["id"] for trigger in updated["triggers"]] == ["manual_launch", "plex_playing"]
    assert len(sequence) == 1
    assert sequence[0]["action"] == "browser_mod.popup"
    content = sequence[0]["data"]["content"]
    assert isinstance(content, str)
    assert all(part in content for part in ("window.top.location.href", "/local/kiosk-marquee.html", "Date.now()"))
    assert "aspect_ratio" not in json.dumps(sequence[0])
    assert any(c.get("condition") == "not" for c in updated["actions"][0]["choose"][0]["conditions"])
    assert plan(updated) == updated


def test_wrapper_keeps_browser_mod_connected_and_has_ha_return():
    source = (Path(__file__).parents[1] / "integrations/homeassistant/kiosk_marquee_wrapper.html").read_text()
    assert all(part in source for part in ("width: 100vw", "height: 100dvh", "src=\"/browser-mod?BrowserID="))
    assert 'href="/dashboard-homepage/0?BrowserID=' in source
    assert "&open=' + Date.now()" in source
