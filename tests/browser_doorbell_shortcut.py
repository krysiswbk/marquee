"""Rendered HA popup shortcut checks at the household kiosk sizes."""

import os
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "REPORTS/marquee-visual-campaign/doorbell-shortcut-batch12"
BASELINE = os.environ.get("MARQUEE_DOORBELL_BASELINE") == "1"
HA_BASE = "http://10.10.9.5:8123/dashboard-homepage"
MARKER = "household-desk-2.12.80"


def state():
    return {
        "fresh": True, "lock": "locked", "sleeping": True,
        "guests": False, "garage_occupied": False,
        "people": [{"name": "Alex", "state": "Home"}],
        "openings": [], "events": [], "cards": [], "alerts": [],
        "timestamp": datetime.now(timezone.utc).timestamp(),
    }


def routes(request):
    url = request.request.url
    if url.startswith(HA_BASE):
        view = "Cameras" if "/cameras" in url else "Home controls"
        return request.fulfill(body=f"<h1>{view}</h1>", content_type="text/html")
    if url.startswith("http://ha.test/dashboard"):
        return request.fulfill(
            body=f'<iframe src="http://marquee.test/kiosk?v={MARKER}" referrerpolicy="no-referrer" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>',
            content_type="text/html", headers={"Referrer-Policy": "no-referrer"},
        )
    path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
    if path in ("/kiosk", "/live"):
        return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
    if path == "/api/brain":
        return request.fulfill(json=state())
    if path in ("/api/config", "/settings.json", "/live-settings.json"):
        return request.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
    if path in ("/ambient.json", "/ha-weather.json"):
        return request.fulfill(json={})
    asset = ROOT / "output" / path.lstrip("/")
    if asset.is_file():
        return request.fulfill(path=str(asset))
    return request.fulfill(json={})


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    dest = EVIDENCE / ("before" if BASELINE else "after")
    dest.mkdir(parents=True, exist_ok=True)
    for width, height in ((1500, 971), (1024, 600)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", routes)
        page.goto("http://ha.test/dashboard", wait_until="domcontentloaded")
        popup = page.frame_locator("iframe")
        popup.locator("body.idle #brain-house[data-state=ready]").wait_for()
        assert popup.locator("body").evaluate("() => document.referrer === ''")
        page.wait_for_timeout(650)
        page.screenshot(path=str(dest / f"ha-popup-{width}x{height}.png"))
        if not BASELINE:
            assert not errors, errors
            assert popup.get_by_role("button", name="Home controls in Home Assistant").count() == 1
            doorbell = popup.get_by_role("button", name="Doorbell camera in Home Assistant")
            assert doorbell.is_visible()
            assert doorbell.inner_text() == "Doorbell"
            home_box = popup.get_by_role("button", name="Home controls in Home Assistant").bounding_box()
            door_box = doorbell.bounding_box()
            dock_box = popup.locator(".brain-dock").bounding_box()
            assert door_box["width"] >= 44 and door_box["height"] >= 44
            assert door_box["x"] >= home_box["x"] + home_box["width"]
            assert door_box["x"] + door_box["width"] <= dock_box["x"] + dock_box["width"]
            assert door_box["y"] >= dock_box["y"] and door_box["y"] + door_box["height"] <= dock_box["y"] + dock_box["height"]
            assert popup.locator(".brain-dock").evaluate("el => el.getBoundingClientRect().top >= document.querySelector('#brain-agenda').getBoundingClientRect().bottom - 1")
            assert popup.locator("html").evaluate("el => el.scrollWidth <= innerWidth")
            doorbell.focus()
            assert doorbell.evaluate("el => el === document.activeElement")
            doorbell.press("Enter")
            page.get_by_role("heading", name="Cameras").wait_for()
            assert page.url == HA_BASE + "/cameras?BrowserID=a38e5c41-b99f0451"
        page.close()

    if not BASELINE:
        for route in ("/kiosk", "/kiosk?display=hubs", "/live?display=garage"):
            page = browser.new_page(viewport={"width": 1024, "height": 600})
            page.route("**/*", routes)
            page.goto("http://marquee.test" + route, wait_until="domcontentloaded")
            page.locator(".brain-dock").wait_for(state="attached")
            assert page.get_by_role("button", name="Doorbell camera in Home Assistant").count() == 0
            assert page.get_by_role("button", name="Home controls in Home Assistant").count() == 0
            page.close()
    browser.close()
    print("PASS: HA popup doorbell route, target, focus, no-referrer and direct/Cast isolation")
