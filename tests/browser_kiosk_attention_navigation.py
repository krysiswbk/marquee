"""Explicit destination navigation remains usable during household alerts."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1600, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            return request.fulfill(json={"providers": {
                "calendar": {"enabled": True, "targets": ["kiosk"]}
            }})
        if path == "/contexts":
            return request.fulfill(json={"contexts": [{
                "id": "calendar:alert-navigation",
                "provider": "calendar",
                "type": "calendar_event",
                "title": "Guest dinner",
                "subtitle": "Today · 6:00 PM",
                "starts": "2099-10-12T22:00:00Z",
                "eventState": "UPCOMING",
            }]})
        if path == "/providers":
            return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        if path == "/now-playing.json":
            return request.fulfill(json={
                "playing": False,
                "state": "idle",
                "attention": {"id": "front-door-open", "urgency": "IMPORTANT"},
            })
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        return request.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    page.wait_for_function("document.body.classList.contains('kiosk-destination-active')")
    page.wait_for_selector(".kiosk-agenda-feature h2")
    assert page.locator("#kiosk-panel").is_visible()
    assert page.locator(".kiosk-agenda-feature h2").inner_text() == "Guest dinner"
    assert page.locator('.kiosk-primary a[data-view="calendar"][aria-current="page"]').count() == 1
    assert page.locator("html").get_attribute("data-kiosk-theme") == "synthwave"
    assert page.locator(".stage").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")

    page.locator('.kiosk-primary a[data-view=""]').click()
    page.wait_for_function("!new URL(location.href).searchParams.has('view')")
    assert page.locator("#kiosk-panel").evaluate("el => el.hidden")
    assert page.locator('.kiosk-primary a[data-view=""][aria-current="page"]').count() == 1
    assert not errors, errors
    browser.close()
    print("PASS: explicit Calendar navigation stays visible during household attention; Home restores the alert dashboard")
