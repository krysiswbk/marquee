"""Responsive browser coverage for the calm Plex idle kiosk composition."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(393, 852), (1024, 600), (1500, 900)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
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
                data = {"providers": {"plex": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}}
            elif path == "/contexts":
                data = {"contexts": []}
            elif path == "/providers":
                data = {"providers": {"plex": {"state": "ok", "candidateContexts": 0,
                                                   "eligibleContexts": 0, "contexts": []}}}
            elif path == "/now-playing.json":
                data = {"playing": False, "state": "idle", "availability": "idle"}
            elif path == "/weather":
                data = {"temp": 15, "condition": "partlycloudy", "code": 2,
                        "daily": [{"temperature": 21, "templow": 12}], "hourly": []}
            elif path in ("/settings.json", "/live-settings.json"):
                data = {"transitionMs": 0}
            elif path == "/ambient.json":
                data = {"opacity": 0}
            else:
                data = {}
            return request.fulfill(body=json.dumps(data), content_type="application/json")

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk?view=plex", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-section:not([hidden]) #kiosk-section-title")
        page.evaluate("""() => {
          document.querySelector('#idle-weather-temp').textContent = '15°C';
          document.querySelector('#idle-weather-condition').textContent = 'Partly cloudy';
          document.querySelector('#idle-weather-range').textContent = 'High 21° / Low 12°';
          window.MarqueeNavigation.resolve({playing:false, state:'idle', availability:'idle'});
        }""")
        assert page.locator("#kiosk-section-title").inner_text() == "Nothing is playing"
        assert page.locator(".kiosk-state-mark").count() == 0
        assert page.locator(".kiosk-now-playing-detail").count() == 0
        assert page.locator(".kiosk-weather-fact").count() == 3
        assert page.locator(".kiosk-weather-separator").count() == 2
        assert page.locator(".kiosk-weather-fact").nth(0).get_attribute("aria-label") == "Temperature: 15°C"
        assert page.locator(".kiosk-weather-fact").nth(2).get_attribute("aria-label") == "High and low: High 21° / Low 12°"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

        page.locator("#kiosk-section-title").focus()
        assert page.evaluate("document.activeElement.id === 'kiosk-section-title'")
        assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle !== 'none'")

        page.evaluate("window.MarqueeNavigation.resolve({playing:false, state:'unavailable', availability:'unavailable'})")
        assert page.locator(".kiosk-state-mark.is-unavailable").count() == 1
        assert page.locator("[data-kiosk-retry]").count() == 1
        page.locator('.kiosk-home-action').click()
        page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
        assert page.locator(".kiosk-section").evaluate("el => el.hidden && el.inert")
        assert not errors, (width, height, errors)
        page.close()
    browser.close()
    print("PASS: Plex idle/unavailable composition, grouped weather, scoped focus, responsive fit, and Home return")
