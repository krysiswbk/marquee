"""The HA recovery action must retain full-screen Marquee on repeat launches."""

import json
import runpy
import sys
from pathlib import Path


def test_recovery_popup_fills_viewport_without_browser_refresh():
    integration = Path(__file__).parents[1] / "integrations/homeassistant"
    sys.path.insert(0, str(integration))
    try:
        plan = runpy.run_path(str(integration / "sync_kiosk_overlay.py"))["plan"]
    finally:
        sys.path.pop(0)
    current = {
        "id": "kiosk_marquee_plex_overlay",
        "actions": [{"choose": [{"sequence": [
            {"action": "browser_mod.popup", "data": {"tag": "marquee", "content": {
                "type": "iframe", "aspect_ratio": "62%", "url": "http://marquee/kiosk"
            }}},
        ]}]}],
    }
    original = json.dumps(current, sort_keys=True)
    updated = plan(current)
    sequence = updated["actions"][0]["choose"][0]["sequence"]
    assert json.dumps(current, sort_keys=True) == original
    assert len(sequence) == 1
    assert sequence[0]["action"] == "browser_mod.popup"
    content = sequence[0]["data"]["content"]
    assert isinstance(content, str)
    assert all(part in content for part in ("position:fixed", "inset:0", "width:100vw", "height:100dvh"))
    assert "aspect_ratio" not in json.dumps(sequence[0])
