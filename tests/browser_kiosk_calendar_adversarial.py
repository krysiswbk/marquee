"""Adversarial full-agenda coverage for global fitting and tall-row reveal."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def run_case(page, width, height, events):
    page.set_viewport_size({"width": width, "height": height})

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
    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')


def event(index, title, subtitle="Next week"):
    return {"id": f"calendar:adversarial-{index}", "provider": "calendar", "type": "calendar_event",
            "subtype": "timed", "title": title, "subtitle": subtitle,
            "starts": f"2099-10-{index + 1:02d}T19:00:00Z", "expires": f"2099-10-{index + 1:02d}T20:00:00Z",
            "eventState": "UPCOMING"}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 430, "height": 852})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    later_long = [event(0, "First agenda event"), event(1, "Second agenda event"),
                  event(2, "Third agenda event"), event(3, "Later page long summary " + "with important details " * 18),
                  event(4, "Fifth agenda event"), event(5, "Sixth agenda event")]
    run_case(page, 430, 852, later_long)
    stable_size = page.locator(".kiosk-calendar-detail").get_attribute("data-page-size")
    stable_pages = page.locator(".kiosk-calendar-count").inner_text().split(" of ")[1]
    seen = []
    while True:
        seen.extend(page.locator(".kiosk-calendar-page .kiosk-agenda-row").all_inner_texts())
        assert page.locator(".kiosk-calendar-detail").get_attribute("data-page-size") == stable_size
        assert page.locator(".kiosk-calendar-count").inner_text().split(" of ")[1] == stable_pages
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
        next_button = page.locator('[data-calendar-control="next"]')
        if next_button.is_disabled():
            break
        next_button.click()
        assert page.evaluate("['next', 'previous'].includes(document.activeElement?.dataset.calendarControl)"), page.evaluate("({tag: document.activeElement?.tagName, control: document.activeElement?.dataset?.calendarControl, text: document.activeElement?.textContent})")
        page.evaluate("window.dispatchEvent(new Event('marquee-surface-rendered'))")
    assert len(seen) == len(set(seen)) == len(later_long)
    assert any("Later page long summary" in text for text in seen)
    assert not errors, errors
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    page.wait_for_selector('[data-calendar-disclosure]')
    page.locator('[data-calendar-disclosure]').click()
    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
    assert page.url.find("mode=all") >= 0
    page.locator('[data-calendar-summary]').click()
    page.wait_for_function("!new URL(location.href).searchParams.has('mode')")
    assert page.evaluate("document.activeElement?.matches('[data-calendar-disclosure]')")
    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
    page.locator('[data-calendar-summary]').click()
    page.wait_for_function("!new URL(location.href).searchParams.has('mode')")
    direct_return_immediate = page.evaluate("document.activeElement?.matches('[data-calendar-disclosure]')")
    assert direct_return_immediate
    page.wait_for_timeout(200)
    direct_return_after_200ms = page.evaluate("document.activeElement?.matches('[data-calendar-disclosure]')")
    assert direct_return_after_200ms
    page.close()

    page = browser.new_page(viewport={"width": 360, "height": 800})
    very_tall = [event(0, "Irreducibly tall entry " + "complete event information " * 140)]
    run_case(page, 360, 800, very_tall)
    agenda = page.locator(".kiosk-calendar-page")
    assert page.locator(".kiosk-calendar-detail").get_attribute("data-page-size") == "1"
    assert agenda.get_attribute("data-calendar-overflow") == "scroll"
    assert agenda.get_attribute("tabindex") == "0"
    assert "Irreducibly tall entry" in agenda.locator(".kiosk-agenda-row").inner_text()
    assert agenda.evaluate("el => el.scrollHeight > el.clientHeight")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
    assert not page.locator('[data-calendar-control="next"]').is_enabled()
    page.close()
    browser.close()
    print(f"PASS: direct-loaded Back to summary disclosure focus immediate={direct_return_immediate}, +200ms={direct_return_after_200ms}; later-page long summary and irreducibly tall capacity-one entry remain reachable without duplicates or horizontal overflow")
