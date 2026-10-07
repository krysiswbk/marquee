"""Release 2.12.7 regression coverage for Calendar rows on shallow screens."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def event(index):
    return {
        "id": f"calendar:release-2-12-7-{index}",
        "provider": "calendar",
        "type": "calendar_event",
        "subtype": "timed",
        "title": f"Release event {index}",
        "subtitle": "Tomorrow",
        "starts": f"2099-10-{index + 1:02d}T19:00:00Z",
        "expires": f"2099-10-{index + 1:02d}T20:00:00Z",
        "eventState": "UPCOMING",
    }


events = [event(index) for index in range(10)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1024, "height": 600}, reduced_motion="reduce")

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/config":
            return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": events})
        if path == "/providers":
            return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        return request.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    page.wait_for_selector("[data-calendar-disclosure]")
    page.locator("[data-calendar-disclosure]").click()
    page.wait_for_selector(".kiosk-calendar-detail")
    agenda = page.locator(".kiosk-calendar-page")
    assert agenda.locator(".kiosk-agenda-row strong").all_inner_texts() == [f"Release event {i}" for i in range(10)]
    assert agenda.evaluate("el => el.scrollHeight > el.clientHeight")
    agenda.evaluate("el => el.scrollTop = el.scrollHeight")
    assert agenda.evaluate("el => el.scrollTop > 0")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
    page.locator("[data-calendar-summary]").click()
    assert page.url.endswith("/kiosk?view=calendar")
    browser.close()
    print("PASS: all ten events stay chronologically ordered in one scrollable agenda on a shallow-wide kiosk display")
