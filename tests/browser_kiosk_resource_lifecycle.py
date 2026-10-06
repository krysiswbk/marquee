"""Independent kiosk resource settlement, retention, and recovery fixture."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    failures = {"contexts": True, "providers": False, "partial": False}

    def route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return route.fulfill(path=str(asset))
        if path == "/api/config":
            return route.fulfill(json={
                "providers": {
                    "weather": {"enabled": True, "targets": ["kiosk"]},
                    "plex": {"enabled": True, "targets": ["kiosk"]},
                },
                "fallback": {},
            })
        if path == "/contexts":
            if failures["contexts"]:
                return route.fulfill(status=503, body="context fixture failure")
            return route.fulfill(json={"contexts": [{
                "id": "weather:one", "provider": "weather", "type": "weather", "title": "Recovered weather",
                "subtitle": "12°", "starts": "2099-01-01T12:00:00Z",
            }]})
        if path == "/providers":
            if failures["providers"]:
                return route.fulfill(status=503, body="provider fixture failure")
            if failures["partial"]:
                return route.fulfill(json={"providers": {
                    "weather": {"state": "degraded", "reason": "weather feed delayed; showing cached observations"},
                    "plex": {"state": "ok"},
                }})
            return route.fulfill(json={"providers": {
                "weather": {"state": "ok"},
                "plex": {"state": "ok"},
            }})
        if path in ("/settings.json", "/live-settings.json"):
            return route.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return route.fulfill(json={"opacity": 0})
        return route.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?view=weather", wait_until="domcontentloaded")
    page.wait_for_selector('[data-lifecycle="disconnected"]')
    assert "context source cannot be reached" in page.locator("[data-lifecycle='disconnected']").inner_text()
    assert page.get_by_role("button", name="Try again").is_visible()
    assert page.get_by_role("link", name="Return to Home", exact=True).is_visible()

    # A recovered config snapshot must clear a warning left by an earlier
    # failed config refresh, even when sibling resources were already healthy.
    page.evaluate("window.MarqueeLifecycle.status('Configuration refresh failed. Showing the last saved settings; retrying.', 'error')")
    page.evaluate("window.MarqueeNavigation.refresh()")
    page.wait_for_function("!document.querySelector('#marquee-lifecycle-status')?.textContent")

    failures["contexts"] = False
    page.evaluate("window.MarqueeNavigation.refresh()")
    page.wait_for_selector('.stage.weather-context #wx-retained-context')
    assert page.locator('.stage.weather-context #wx-retained-context').inner_text() == "Recovered weather"
    assert sum(item.is_visible() for item in page.locator('[data-lifecycle]').all()) == 0

    failures["partial"] = True
    page.evaluate("window.MarqueeNavigation.refresh()")
    partial = page.locator('#weather-lifecycle .kiosk-state[data-lifecycle="partial"]')
    page.wait_for_selector('#weather-lifecycle .kiosk-state[data-lifecycle="partial"]')
    assert partial.is_visible()
    assert "cached observations" in partial.inner_text()
    assert "PARTIAL" in page.locator(".kiosk-brand").inner_text()
    retained = page.locator('.stage.weather-context #wx-retained-context')
    assert retained.is_visible()
    assert page.get_by_role("button", name="Try again").is_visible()
    home = page.locator('#weather-lifecycle').get_by_role("link", name="Return to Home", exact=True)
    assert home.is_visible()
    page.get_by_role("button", name="Try again").focus()
    assert page.evaluate("document.activeElement?.matches('[data-kiosk-retry]')")
    assert page.get_by_role("button", name="Try again").bounding_box()["width"] > 0
    assert home.bounding_box()["width"] > 0

    failures["partial"] = False
    page.evaluate("window.MarqueeNavigation.refresh()")
    page.wait_for_function("!document.querySelector('.kiosk-brand').textContent.includes('delayed')")
    assert page.locator('.stage.weather-context #wx-retained-context').is_visible()
    page.close()
    browser.close()
    print("PASS: config/context/provider failures settle independently and recover without erasing context data")
