"""Deterministic browser coverage for configuration action lifecycles."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
LIVE = (ROOT / "cast/live-layout.html").read_text()
DRAFT = (ROOT / "output/settings-draft.js").read_text()
SHELL = (ROOT / "output/control-shell.js").read_text()
NUMERIC = (ROOT / "output/numeric-controls.js").read_text()
FRAME = "<!doctype html><html><body><main>fixture preview</main><script>window.addEventListener('message', () => {});</script></body></html>"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"),
        args=["--no-sandbox"],
    )
    page = browser.new_page(viewport={"width": 393, "height": 852})
    settings = {
        "liveTheme": "studio",
        "liveLayout": {"home": {"clock": {"x": 0}}},
        "liveVisibility": {"home": {"clock": True}},
        "clockFormat": "12h",
        "clockSeconds": False,
    }
    fail_save = {"value": False}

    def route(route):
        request = route.request
        path = request.url.split("/", 3)[-1].split("?", 1)[0]
        if path == "settings/layout":
            return route.fulfill(body=LIVE, content_type="text/html")
        if path == "settings-draft.js":
            return route.fulfill(body=DRAFT, content_type="application/javascript")
        if path == "control-shell.js":
            return route.fulfill(body=SHELL, content_type="application/javascript")
        if path == "numeric-controls.js":
            return route.fulfill(body=NUMERIC, content_type="application/javascript")
        if path in {"control-shell.css", "control-shell-narrow.css"}:
            return route.fulfill(body="", content_type="text/css")
        if path == "live-settings.json":
            return route.fulfill(body=json.dumps(settings), content_type="application/json")
        if path == "live-settings":
            if fail_save["value"]:
                return route.fulfill(status=500, body=json.dumps({"error": "fixture save failed"}), content_type="application/json")
            settings.update(request.post_data_json)
            return route.fulfill(body=json.dumps({"ok": True, "settings": settings}), content_type="application/json")
        if path == "live":
            return route.fulfill(body=FRAME, content_type="text/html")
        return route.abort()

    page.route("**/*", route)
    page.goto("http://fixture.test/settings/layout?profile=live")
    page.locator("#save").wait_for()
    page.wait_for_timeout(500)
    assert page.locator("#save").is_disabled()
    assert page.locator("#discard").is_disabled()

    page.locator("#liveTheme").select_option("afterhours")
    assert not page.locator("#save").is_disabled()
    assert not page.locator("#discard").is_disabled()

    page.locator("#discard").click()
    page.wait_for_timeout(100)
    assert page.locator("#save").is_disabled()
    assert "Draft discarded" in page.locator("#status").inner_text()

    page.locator("#liveTheme").select_option("dispatch")
    fail_save["value"] = True
    page.locator("#save").click()
    page.wait_for_timeout(500)
    page.wait_for_function("document.querySelector('#status').textContent.includes('Save failed')", timeout=3000)
    assert not page.locator("#save").is_disabled()
    assert not page.locator("#discard").is_disabled()

    fail_save["value"] = False
    page.locator("#save").click()
    page.wait_for_function("document.querySelector('#status').textContent.includes('Saved —')")
    assert page.locator("#save").is_disabled()
    assert page.locator("#discard").is_disabled()
    assert page.locator("#status").get_attribute("role") == "status"
    print("393x852: Live pristine, dirty, discard, failed save, successful save PASS")
    browser.close()
