"""Wall display regression for long Calendar titles and recent activity."""

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
LONG_TITLE = "Garbage, blue box, green cart, bulk waste (3 items max), and yard waste"


def bounds(page, selector):
    return page.locator(selector).evaluate("el => { const r = el.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight}; }")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    for width, height in ((1024, 600), (1280, 720)):
        page = browser.new_page(viewport={"width": width, "height": height})

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/kiosk", "/live"):
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/config":
                return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
            if path == "/contexts":
                return request.fulfill(json={"contexts": [
                    {"id": "garbage:1", "provider": "calendar", "type": "calendar_event", "title": LONG_TITLE,
                     "subtitle": "Today", "starts": "2099-10-19T12:00:00Z"},
                    {"id": "moon:1", "provider": "calendar", "type": "calendar_event", "title": "Full Moon",
                     "subtitle": "Sunday, Oct 25", "starts": "2099-10-25T20:00:00Z"},
                    {"id": "garbage:2", "provider": "calendar", "type": "calendar_event", "title": "Blue box and green cart",
                     "subtitle": "Monday, Oct 26", "starts": "2099-10-26T12:00:00Z"},
                ]})
            if path == "/providers":
                return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
            if path == "/api/brain":
                return request.fulfill(json={"fresh": True, "openings": [], "events": [
                    {"id": f"event:{i}", "title": name, "at": time.time() - 120 - i * 60, "expires": time.time() + 3600}
                    for i, name in enumerate(("Garage Door closed", "Front door lock locked", "Front Door closed", "Patio Door closed"))
                ], "cards": [], "alerts": [], "people": []})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_selector("#brain-events .brain-event")
        activity, feed = bounds(page, "#brain-activity"), bounds(page, ".brain-dock")
        if width == 1024:
            page.screenshot(path="/tmp/marquee-home-overflow-fixed.png")
        assert activity["bottom"] < feed["top"], (width, activity, feed)
        assert activity["clientHeight"] >= activity["scrollHeight"] - 1, (width, activity)

        page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-agenda-feature h2")
        title = bounds(page, ".kiosk-agenda-feature h2")
        card = bounds(page, ".kiosk-agenda-feature")
        if width == 1024:
            page.screenshot(path="/tmp/marquee-calendar-summary-overflow-fixed.png")
        assert title["bottom"] < card["bottom"], (width, title, card)
        assert card["bottom"] <= bounds(page, ".brain-dock")["top"] or page.locator("#kiosk-panel").evaluate("el => el.scrollHeight > el.clientHeight"), (width, card)

        page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-calendar-controls")
        controls, feed = bounds(page, ".kiosk-calendar-controls"), bounds(page, ".brain-dock")
        if width == 1024:
            page.screenshot(path="/tmp/marquee-calendar-detail-overflow-fixed.png")
        assert controls["bottom"] < feed["top"], (width, controls, feed)
        assert page.locator(".kiosk-calendar-page .kiosk-agenda-row strong").first.inner_text() == LONG_TITLE
        page.close()

    dashboard = browser.new_page(viewport={"width": 1024, "height": 600})
    visits = {"count": 0}

    def embedded_route(request):
        url = request.request.url
        if url.startswith("http://hass.test/"):
            visits["count"] += 1
            body = '<title>Home Assistant</title><iframe src="http://marquee.test/kiosk" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>' if visits["count"] == 1 else '<title>Home Assistant</title><h1>Dashboard</h1>'
            return request.fulfill(content_type="text/html", body=body)
        path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path == "/kiosk":
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/brain":
            return request.fulfill(json={"fresh": True, "openings": [], "events": [], "cards": [], "alerts": [], "people": []})
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        return request.fulfill(json={})

    dashboard.route("**/*", embedded_route)
    dashboard.goto("http://hass.test/dashboard-homepage/0", wait_until="domcontentloaded")
    close = dashboard.frame_locator("iframe").locator(".brain-dock-close")
    close.wait_for(state="visible")
    assert close.inner_text() == "✕ Close"
    close.click()
    dashboard.get_by_role("heading", name="Dashboard").wait_for()
    assert visits["count"] >= 2
    dashboard.close()
    browser.close()
    print("PASS: shallow Calendar and Home fit; embedded Close returns to dashboard")
