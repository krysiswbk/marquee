"""Browser regression for clearing cross-field validation descriptions."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    profile = {
        "template": "spotlight", "theme": "amber", "liveTheme": "studio",
        "clockFormat": "12h", "clockSeconds": False, "showWeather": True,
        "weatherUnits": "c", "displayWidth": 1280, "displayHeight": 720,
    }
    config = {"fallback": {"rotation_seconds": 300, "single_item_seconds": 15}}

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        asset = ROOT / ("cast/settings-control.html" if path == "/settings" else Path("output") / path.lstrip("/"))
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/settings.json" or path == "/live-settings.json":
            return request.fulfill(body=json.dumps(profile), content_type="application/json")
        if path == "/api/config":
            return request.fulfill(
                body=json.dumps(config),
                content_type="application/json",
            )
        if path == "/providers":
            return request.fulfill(body=json.dumps({"providers": {}}), content_type="application/json")
        if path in {"/api/brain", "/healthz", "/api/attention"}:
            return request.fulfill(status=404, body="")
        if path in {"/settings", "/live-settings"}:
            return request.fulfill(body=json.dumps({}), content_type="application/json")
        return request.abort()

    page.route("**/*", route)
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.goto("http://marquee.test/settings#displays")
    page.wait_for_selector("#app:not([hidden])")
    assert page.evaluate("typeof window.MarqueeNumericControls.enhance") == "function"
    assert not any("MarqueeNumericControls" in error for error in page_errors)

    item = page.locator("#fallback-item")
    rotation = page.locator("#fallback-rotation")
    save = page.locator('.savebar[data-area="displays"] .save-area')
    item.evaluate("input => { input.closest('details').open = true; }")

    item.fill("999")
    save.click()
    page.wait_for_selector("#fallback-item-error")
    assert item.get_attribute("aria-invalid") == "true"
    assert "fallback-item-error" in item.get_attribute("aria-describedby").split()

    item.fill("15")
    rotation.fill("1")
    save.click()
    page.wait_for_selector("#fallback-rotation-error")
    assert not page.locator("#fallback-item-error").count()
    assert item.get_attribute("aria-invalid") is None
    described_by = (item.get_attribute("aria-describedby") or "").split()
    assert "fallback-item-error" not in described_by
    assert item.evaluate(
        """(input) => (input.getAttribute('aria-describedby') || '').split(/\\s+/).filter(Boolean)
        .every(id => document.getElementById(id))"""
    )

    page.locator('button[data-profile="live"]').click()
    assert page.locator("#live-theme").is_enabled()
    assert page.locator("#template").is_disabled()

    page.locator('#tab-content').click()
    displays = page.locator('#panel-displays')
    assert displays.get_attribute("hidden") == ""
    assert displays.get_attribute("inert") == ""
    assert all(control.is_disabled() for control in displays.locator("input, select, textarea, button").all())

    page.locator("#interest-sports-teams").evaluate("input => { input.closest('details').open = true; }")
    page.locator("#interest-sports-teams").fill("TOR")
    page.locator('#panel-content input[required]').evaluate_all(
        """inputs => inputs.forEach(input => {
            if (input.value) return;
            input.value = input.type === 'url' ? 'https://example.test' :
                input.type === 'number' ? (input.min || '1') : 'fixture';
            input.dispatchEvent(new Event('input', {bubbles: true}));
        })"""
    )
    page.locator('.savebar[data-area="content"] .save-area').click()
    page.wait_for_function("document.querySelector('.savebar[data-area=content] .area-status').textContent.includes('Saved')")
    assert displays.get_attribute("hidden") == ""
    assert displays.get_attribute("inert") == ""
    assert all(control.is_disabled() for control in displays.locator("input, select, textarea, button").all())

    page.locator('#tab-displays').click()
    assert page.locator("#panel-displays").get_attribute("hidden") is None
    assert page.locator("#panel-displays").get_attribute("inert") is None
    assert page.locator("#live-theme").is_enabled()
    assert page.locator("#template").is_disabled()

    browser.close()
    print("PASS: validation recovery and inactive Displays tab ownership/profile round trips")
