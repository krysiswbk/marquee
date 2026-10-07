"""Adversarial full-agenda coverage for the scrollable Calendar list."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def event(index, title, subtitle="Next week"):
    return {"id": f"calendar:adversarial-{index}", "provider": "calendar", "type": "calendar_event",
            "subtype": "timed", "title": title, "subtitle": subtitle,
            "starts": f"2099-10-{index + 1:02d}T19:00:00Z", "expires": f"2099-10-{index + 1:02d}T20:00:00Z",
            "eventState": "UPCOMING"}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 393, "height": 852})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    events = [event(index, f"Event {index}") for index in range(12)]

    def route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/config":
            return route.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}})
        if path == "/contexts":
            return route.fulfill(json={"contexts": events})
        if path == "/providers":
            return route.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return route.fulfill(path=str(asset))
        return route.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    page.wait_for_selector("[data-calendar-disclosure]")
    # The existing summary remains the same featured event plus compact preview.
    assert page.locator(".kiosk-agenda-feature h2").inner_text() == "Event 0"
    assert page.locator(".kiosk-agenda-more").inner_text() == "View all 12 events"
    page.locator("[data-calendar-disclosure]").click()
    page.wait_for_selector(".kiosk-calendar-detail")

    agenda = page.locator(".kiosk-calendar-page")
    assert page.locator(".kiosk-calendar-count").inner_text() == "12 events"
    assert agenda.locator(".kiosk-agenda-row strong").all_inner_texts() == [f"Event {i}" for i in range(12)]
    assert agenda.evaluate("el => getComputedStyle(el).overflowY === 'auto'")
    assert agenda.evaluate("el => el.scrollHeight > el.clientHeight")
    agenda.evaluate("el => { el.scrollTop = el.scrollHeight; }")
    assert agenda.evaluate("el => el.scrollTop > 0")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
    assert not page.locator('[data-calendar-control="next"]').count()
    assert "mode=all" in page.url and "page=" not in page.url

    # Refresh keeps the scrollable agenda and all events in order.
    page.evaluate("MarqueeNavigation.refresh()")
    assert page.locator(".kiosk-calendar-page .kiosk-agenda-row strong").all_inner_texts() == [f"Event {i}" for i in range(12)]
    page.locator("[data-calendar-summary]").click()
    page.wait_for_function("!new URL(location.href).searchParams.has('mode')")
    assert page.evaluate("document.activeElement?.matches('[data-calendar-disclosure]')")
    assert not errors, errors

    # A single very long title/details row remains inside the agenda scrollport.
    long_page = browser.new_page(viewport={"width": 360, "height": 800})
    long_events = [event(0, "Long event " + "complete event information " * 80)]

    def long_route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/config":
            return route.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
        if path == "/contexts":
            return route.fulfill(json={"contexts": long_events})
        if path == "/providers":
            return route.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return route.fulfill(path=str(asset))
        return route.fulfill(json={})

    long_page.route("**/*", long_route)
    long_page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    long_agenda = long_page.locator(".kiosk-calendar-page")
    assert long_agenda.evaluate("el => el.scrollHeight >= el.clientHeight")
    assert long_page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
    long_page.close()
    page.close()
    browser.close()
    print("PASS: summary unchanged; all 12 events render once in a single scrollable agenda across refresh; long rows remain contained; Back to summary focus and browser history remain correct")
