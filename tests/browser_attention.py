"""Smoke test against an isolated running app; never point this at household displays.
MARQUEE_SMOKE_URL must be a loopback URL with the documented test_leak binding.
"""
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright

base = os.environ.get("MARQUEE_SMOKE_URL", "http://127.0.0.1:18084")
assert urlparse(base).hostname in ("127.0.0.1", "localhost"), "Only isolated loopback instances"


def api(path, body=None, method=None):
    req = Request(base + path, data=json.dumps(body).encode() if body else None,
                  headers={"Content-Type": "application/json"}, method=method)
    with urlopen(req, timeout=5) as response:
        return json.load(response)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/admin/attention")
    page.wait_for_function("document.getElementById('status').textContent.startsWith('Updated')")
    api("/api/attention/signals", {"states": [{"entity_id": "binary_sensor.test_leak", "state": "on"}], "full": True})
    for display in ("kiosk", "hubs", "garage"):
        selected = api("/now-playing.json?display=" + display)
        assert selected["attention"]["urgency"] == "CRITICAL", selected
    page.wait_for_selector("#items button")
    page.locator("#items button").filter(has_text="acknowledge").click()
    page.wait_for_function("document.getElementById('items').textContent.includes('ACKNOWLEDGED')")
    assert api("/now-playing.json?display=hubs")["playing"]
    page.screenshot(path="/tmp/marquee-brain-debugger.png", full_page=True)
    page.goto(base + "/live")
    page.get_by_text("Test leak detected", exact=True).first.wait_for(state="visible")
    page.wait_for_timeout(1200)
    page.screenshot(path="/tmp/marquee-brain-critical.png")
    api("/api/attention/signals", {"states": [{"entity_id": "binary_sensor.test_leak", "state": "off"}], "full": True})
    for display in ("kiosk", "hubs", "garage"):
        assert "attention" not in api("/now-playing.json?display=" + display)
    page.get_by_text("Test leak detected", exact=True).first.wait_for(state="hidden")
    assert not errors, errors
    print("PASS: real app ingestion, all display feeds, debugger, acknowledgement, critical render, immediate resolution")
    browser.close()
