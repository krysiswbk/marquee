"""Dashboard settles a cold-start brain failure and recovers through retry."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1024, "height": 768})
    failed = {"brain": True}
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

    def route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/live", "/kiosk"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/brain" and failed["brain"]:
            return route.fulfill(status=200, body="not json", content_type="application/json")
        if path == "/api/brain":
            return route.fulfill(json={"fresh": True, "openings": [], "events": [], "cards": [], "alerts": [], "people": []})
        if path in ("/api/config", "/contexts", "/providers", "/settings.json", "/live-settings.json", "/ambient.json", "/ha-weather.json"):
            return route.fulfill(json={"providers": {}, "contexts": []})
        if path == "/events":
            return route.fulfill(body="", content_type="text/event-stream")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return route.fulfill(path=str(asset))
        return route.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/live", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#brain-house')?.dataset.state === 'disconnected'")
    assert page.locator("#brain-connection").inner_text() == "HOUSE FEED OFFLINE"
    assert page.locator("#brain-retry").is_visible()
    assert page.locator(".brain-weather-link").get_attribute("href") == "/live?view=weather"

    failed["brain"] = False
    page.locator("#brain-retry").click()
    page.wait_for_function("document.querySelector('#brain-house')?.dataset.state === 'ready'")
    assert page.locator("#brain-connection").inner_text() == "HOUSE CONNECTED"
    assert page.locator("#brain-retry").is_hidden()
    assert not errors, errors
    page.close()
    browser.close()
    print("PASS: dashboard cold-start failure is disconnected and retry recovers")
