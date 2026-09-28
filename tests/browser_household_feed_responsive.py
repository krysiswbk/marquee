"""Responsive truth/readability contract for the persistent household feed."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(320, 720), (360, 720), (393, 852), (430, 852),
             (481, 900), (700, 900), (1024, 600), (1500, 900)]
UNKNOWN = ["Nursery Window", "Office Window", "Basement Window",
           "Garage Entry", "Patio Door", "Workshop Door"]
HEALTH = ["Nursery Motion & Lux Motion — Upstairs Hallway",
          "Nursery Window Contact — South-facing Window"]


def snapshot(kind):
    if kind == "disconnected":
        return {"fresh": False, "openings": [], "events": [], "cards": [],
                "alerts": [], "people": []}
    if kind == "unknown":
        return {"fresh": True, "unknown": UNKNOWN, "events": [], "cards": [],
                "alerts": [], "people": []}
    if kind == "event":
        return {"fresh": True, "unknown": [], "events": [{
            "id": "fixture:event", "title": "Front door lock state changed after remote reconnect with a very long explanation",
            "at": 0, "expires": 4102444800,
        }], "cards": [], "alerts": [], "people": []}
    if kind == "health":
        return {"fresh": True, "unknown": [], "device_health": [
            {"entity_id": f"sensor.health_{index}", "name": name,
             "state": "unavailable", "location": "nursery"}
            for index, name in enumerate(HEALTH)],
                "events": [], "cards": [], "alerts": [], "people": []}
    if kind == "health_one":
        return {"fresh": True, "unknown": [], "device_health": [
            {"entity_id": "sensor.health_one", "name": "Nursery Motion & Lux Motion — Upstairs Hallway",
             "state": "unavailable", "location": "nursery"}],
                "events": [], "cards": [], "alerts": [], "people": []}
    return {"fresh": True, "unknown": [], "events": [], "cards": [{
        "type": "calendar_event", "title": "Annual neighbourhood association planning meeting and accessibility review",
        "subtitle": "Tomorrow · 7:00 PM",
    }], "alerts": [], "people": []}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        for kind in ("unknown", "health", "health_one", "disconnected", "event", "calendar"):
            page = browser.new_page(viewport={"width": width, "height": height})

            def route(route):
                request = route.request
                url = request.url
                path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path in ("/kiosk", "/live"):
                    return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                if path == "/api/brain":
                    return route.fulfill(json=snapshot(kind))
                if path in ("/api/config", "/settings.json", "/live-settings.json"):
                    return route.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
                if path in ("/ambient.json", "/ha-weather.json"):
                    return route.fulfill(json={})
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return route.fulfill(path=str(asset))
                return route.fulfill(json={})

            page.route("**/*", route)
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto("http://marquee.test/live", wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            assert not page_errors, page_errors
            assert page.locator("#brain-dock-copy").count() == 1
            assert page.locator("#brain-dock-copy").get_attribute("data-full-text")
            copy = page.locator("#brain-dock-copy")
            full = copy.get_attribute("data-full-text")

            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator(".brain-dock").evaluate("el => el.scrollWidth <= el.clientWidth")
            assert copy.get_attribute("aria-label") == full
            assert copy.get_attribute("title") == full

            if kind == "unknown":
                if width <= 430:
                    assert copy.inner_text() == "6 devices not reporting"
                elif width <= 700:
                    assert copy.inner_text() == "Not reporting: Nursery Window, Office Window + 4 more devices"
                else:
                    assert copy.inner_text() == full
                assert full == "Not reporting: " + ", ".join(UNKNOWN)
            elif kind in ("health", "health_one"):
                count = 2 if kind == "health" else 1
                if width <= 430:
                    assert copy.inner_text() == f"{count} device{'s' if count != 1 else ''} offline · Check connection"
                elif width <= 700:
                    assert copy.inner_text().startswith("Offline: ")
                    assert "Check connection." in copy.inner_text()
                    assert all(name not in copy.inner_text() for name in (HEALTH if kind == "health" else [HEALTH[0]]))
                else:
                    assert copy.inner_text() == full
                assert full == "Offline: " + ", ".join(name for name in (HEALTH if kind == "health" else ["Nursery Motion & Lux Motion — Upstairs Hallway"])) + ". Check batteries or connection."
                assert copy.get_attribute("aria-label") == full
                assert page.locator("#brain-device-health").inner_text() == full
            elif kind == "disconnected":
                assert copy.inner_text() == "Household connection lost · Current states unavailable" if width <= 700 else copy.inner_text() == full
                assert full == "Household connection lost · Current door and lock states are unknown"
            elif kind == "event":
                assert "Recent event:" in copy.inner_text() if width <= 700 else "Front door lock state changed" in copy.inner_text()
                assert "Front door lock state changed after remote reconnect with a very long explanation" in full
            else:
                assert "Calendar:" in copy.inner_text() if width <= 700 else "Annual neighbourhood association" in copy.inner_text()
                assert "accessibility review" in full

            if width <= 700:
                assert copy.evaluate("el => getComputedStyle(el).whiteSpace === 'normal'")
            if kind == "health" and width in (320, 700, 1500):
                page.screenshot(path=f"/tmp/marquee-2.10.67-household-{width}x{height}.png")
            page.close()
    browser.close()
    print("PASS: household feed summaries, full text, overflow, and desktop wording hold across target widths")
