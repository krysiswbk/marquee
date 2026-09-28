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
    evidence = []
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
                    *[{"id": f"calendar:item-{index}", "provider": "calendar", "type": "calendar_event",
                       "subtype": "timed", "title": f"Agenda item {index}", "subtitle": "Next week",
                       "starts": f"2099-10-{index + 2:02d}T19:00:00Z", "expires": f"2099-10-{index + 2:02d}T20:00:00Z",
                       "eventState": "UPCOMING"} for index in range(1, 10)],
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
        page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
        stable_count = page.locator(".kiosk-calendar-count").inner_text()
        stable_size = page.locator(".kiosk-calendar-detail").get_attribute("data-page-size")
        page.evaluate("window.dispatchEvent(new Event('marquee-surface-rendered'))")
        page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
        assert page.locator(".kiosk-calendar-count").inner_text() == stable_count
        assert page.locator(".kiosk-calendar-detail").get_attribute("data-page-size") == stable_size
        seen = []
        visited_pages = 0
        while True:
            visited_pages += 1
            agenda = page.locator(".kiosk-calendar-page")
            assert agenda.evaluate("el => el.scrollHeight <= el.clientHeight + 1"), (width, height, agenda.bounding_box())
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
            if visited_pages == 1:
                birthday = agenda.locator(".kiosk-agenda-row.is-birthday")
                assert birthday.count() == 1
                assert birthday.locator(".kiosk-birthday-rows li").all_inner_texts() == list(BIRTHDAYS[1:])
                assert birthday.inner_text().count("Birthday") == 1
            seen.extend(agenda.locator(".kiosk-agenda-row").all_inner_texts())
            next_button = page.locator('[data-calendar-control="next"]')
            if next_button.is_disabled():
                break
            current = page.locator(".kiosk-calendar-count").inner_text()
            next_button.click()
            page.wait_for_function("old => document.querySelector('.kiosk-calendar-count')?.innerText !== old", arg=current)
            assert page.locator(".kiosk-calendar-detail").get_attribute("data-page-size") == stable_size
            assert page.locator(".kiosk-calendar-count").inner_text().split(" of ")[1] == stable_count.split(" of ")[1]
            page.evaluate("window.dispatchEvent(new Event('marquee-surface-rendered'))")
            assert page.locator(".kiosk-calendar-detail").get_attribute("data-page-size") == stable_size
        combined = "\n".join(seen)
        assert all(name in combined for name in BIRTHDAYS), (width, height, seen)
        assert "Annual meeting" in combined
        assert len(seen) == len(set(seen)), (width, height, seen)
        assert page.locator('[data-calendar-control="previous"]').is_enabled() == (visited_pages > 1)
        assert page.locator('[data-calendar-control="next"]').is_disabled()
        assert not page_errors, (width, height, page_errors)
        evidence.append((width, height, stable_count, stable_size, visited_pages))
        page.close()
    browser.close()
    print(f"PASS: Calendar agenda settlement stable across target viewports: {evidence}")
