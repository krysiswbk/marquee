"""Rendered full-agenda coverage for the CalendarProvider birthday rollup."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(360, 800), (430, 852), (700, 900), (1024, 600), (1500, 900)]
BIRTHDAYS = ("Casey’s birthday", "Jordan · In 6 days", "Sam · In 12 days")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})

        def route(route):
            path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/kiosk", "/live"):
                return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/config":
                return route.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}})
            if path == "/contexts":
                return route.fulfill(json={"contexts": [
                    {"id": "calendar:birthdays", "provider": "calendar", "type": "calendar_event",
                     "subtype": "birthday_rollup", "title": BIRTHDAYS[0],
                     "subtitle": "Tomorrow · Sep 29", "starts": "2099-09-29T04:00:00Z",
                     "expires": "2099-09-30T04:00:00Z", "rows": list(BIRTHDAYS[1:]),
                     "eventState": "UPCOMING"},
                    {"id": "calendar:meeting", "provider": "calendar", "type": "calendar_event",
                     "subtype": "timed", "title": "Annual meeting", "subtitle": "Saturday · 7:00 PM",
                     "starts": "2099-10-01T23:00:00Z", "expires": "2099-10-02T01:00:00Z",
                     "eventState": "UPCOMING"},
                ]})
            if path == "/providers":
                return route.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return route.fulfill(path=str(asset))
            return route.fulfill(json={})

        page.route("**/*", route)
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-calendar-detail")
        seen = []
        visited_pages = 0
        while True:
            visited_pages += 1
            agenda = page.locator(".kiosk-calendar-page")
            assert agenda.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), (width, height, agenda.bounding_box())
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
            seen.extend(agenda.locator(".kiosk-agenda-row").all_inner_texts())
            next_button = page.locator('[data-calendar-control="next"]')
            if next_button.is_disabled():
                break
            current = page.locator(".kiosk-calendar-count").inner_text()
            next_button.click()
            page.wait_for_timeout(100)
            assert page.locator(".kiosk-calendar-count").inner_text() != current, (width, height, current, page.locator(".kiosk-calendar-count").inner_text(), page_errors)
        combined = "\n".join(seen)
        assert all(name in combined for name in BIRTHDAYS), (width, height, seen)
        assert "Annual meeting" in combined
        assert page.locator('[data-calendar-control="previous"]').is_enabled() == (visited_pages > 1)
        assert page.locator('[data-calendar-control="next"]').is_disabled()
        page.close()
    browser.close()
    print("PASS: CalendarProvider birthday rollup entries remain reachable and fit every target viewport")
