"""An alert entity can be added or removed through the visible JSON editor."""

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cast"))
from marquee.attention.schema import DEFAULT, FORM_SCHEMA, validate  # noqa: E402


def test_alert_entity_json_editor():
    config = validate(DEFAULT)
    config["signal_bindings"] = [{"entity_id": "binary_sensor.front_door", "category": "exterior_door", "location": "entrance"}]
    saved = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1024, "height": 768})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/settings/attention":
                return request.fulfill(path=str(ROOT / "cast/attention-settings.html"), content_type="text/html")
            if path == "/api/attention":
                return request.fulfill(json={"config": config, "enabled": True, "items": [], "signals": [],
                                             "displays": {}, "context": {}, "history": [], "input_schema": FORM_SCHEMA})
            if path == "/api/attention/config":
                incoming = request.request.post_data_json
                config.clear()
                config.update(validate(incoming))
                saved.append(incoming)
                return request.fulfill(json={"ok": True})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(status=404)

        page.route("**/*", route)
        page.goto("http://marquee.test/settings/attention#alert-entities-json")
        page.wait_for_function("document.querySelector('#signal-bindings-json').value.includes('front_door')")
        assert page.locator("#alert-entities-json").get_attribute("open") is not None
        page.screenshot(path="/tmp/marquee-alert-entities-editor.png")
        editor = page.locator("#signal-bindings-json")
        editor.fill("not JSON")
        assert editor.get_attribute("aria-invalid") == "true"
        assert page.locator("#save").is_disabled()
        assert page.locator("#signal-bindings-json-error").is_visible()

        bindings = [
            {"entity_id": "binary_sensor.front_door", "category": "exterior_door", "location": "entrance"},
            {"entity_id": "binary_sensor.nursery_door", "category": "maintenance", "location": "nursery"},
        ]
        editor.fill(json.dumps(bindings))
        assert editor.get_attribute("aria-invalid") is None
        assert page.locator("#save").is_enabled()
        assert "2 bindings" in page.locator("#signal-binding-count").inner_text()
        page.locator("#save").click()
        page.wait_for_function("document.querySelector('#save-status').textContent.includes('saved') && document.querySelector('#save').disabled")
        assert [item["entity_id"] for item in saved[-1]["signal_bindings"]] == [
            "binary_sensor.front_door", "binary_sensor.nursery_door"
        ]

        editor.fill(json.dumps(bindings[1:]))
        page.locator("#save").click()
        page.wait_for_function("document.querySelector('#save-status').textContent.includes('saved') && document.querySelector('#save').disabled")
        assert [item["entity_id"] for item in saved[-1]["signal_bindings"]] == ["binary_sensor.nursery_door"]
        assert not errors, errors
        browser.close()
