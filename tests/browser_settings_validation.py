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

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        asset = ROOT / ("cast/settings-control.html" if path == "/settings" else "output" / path.lstrip("/"))
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/settings.json" or path == "/live-settings.json":
            return request.fulfill(body=json.dumps({}), content_type="application/json")
        if path == "/api/config":
            return request.fulfill(
                body=json.dumps({"fallback": {"rotation_seconds": 300, "single_item_seconds": 15}}),
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
    page.goto("http://marquee.test/settings#displays")
    page.wait_for_selector("#app:not([hidden])")

    item = page.locator("#fallback-item")
    rotation = page.locator("#fallback-rotation")
    save = page.locator('.savebar[data-area="displays"] .save-area')

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

    browser.close()
    print("PASS: recovered first numeric control loses its error node and aria-describedby token")
