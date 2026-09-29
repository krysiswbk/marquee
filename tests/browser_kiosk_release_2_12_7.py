"""Release 2.12.7 contracts for Calendar settlement semantics and short-wide density."""

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
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")

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

    transitional = page.evaluate("""() => {
        const controls = [...document.querySelectorAll('[data-calendar-control]')];
        const next = document.querySelector('[data-calendar-control="next"]');
        const before = location.href;
        next.click();
        return {
            layout: document.querySelector('.kiosk-calendar-detail')?.dataset.calendarLayout,
            disabled: controls.map(control => control.disabled),
            aria: controls.map(control => control.getAttribute('aria-disabled')),
            tabbable: controls.some(control => !control.disabled && control.tabIndex >= 0),
            unchanged: location.href === before,
        };
    }""")
    assert transitional == {
        "layout": "settling",
        "disabled": [True, True],
        "aria": ["true", "true"],
        "tabbable": False,
        "unchanged": True,
    }, transitional

    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
    assert page.locator('[data-calendar-control="previous"]').is_disabled()
    assert page.locator('[data-calendar-control="previous"]').get_attribute("aria-disabled") == "true"
    assert page.locator('[data-calendar-control="next"]').is_enabled()
    assert page.locator('[data-calendar-control="next"]').get_attribute("aria-disabled") == "false"
    assert page.locator(".kiosk-calendar-count").inner_text() == "Page 1 of 4"

    page.set_viewport_size({"width": 1024, "height": 600})
    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
    assert page.locator(".kiosk-calendar-count").inner_text() == "Page 1 of 3"

    seen = []
    page_counts = []
    while True:
        page_counts.append(page.locator(".kiosk-calendar-count").inner_text())
        seen.extend(page.locator(".kiosk-calendar-page .kiosk-agenda-row strong").all_inner_texts())
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight")
        assert page.locator(".kiosk-calendar-page").evaluate("el => el.scrollHeight <= el.clientHeight + 1")
        assert page.locator(".kiosk-calendar-page .kiosk-agenda-row").evaluate_all(
            "rows => rows.every(row => { const a = row.getBoundingClientRect(); const b = row.parentElement.parentElement.getBoundingClientRect(); return a.top >= b.top - 1 && a.bottom <= b.bottom + 1; })"
        )
        next_button = page.locator('[data-calendar-control="next"]')
        if next_button.is_disabled():
            break
        next_button.click()
    assert seen == [f"Release event {index}" for index in range(10)]
    assert len(page_counts) == 3 and len(page_counts) < 10

    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail[data-calendar-layout="settled"]')
    assert page.locator(".kiosk-calendar-count").inner_text() == "Page 1 of 3"
    page.locator('[data-calendar-control="next"]').click()
    assert page.url.endswith("/kiosk?view=calendar&mode=all&page=2")
    assert page.evaluate("document.activeElement?.dataset.calendarControl === 'next'")
    assert not page.locator(".kiosk-calendar-page .kiosk-agenda-row").count() == 0
    browser.close()
    print("PASS: unsettled pagination is natively/semantically disabled; ten short-wide events remain ordered, reachable once, clipped-free, and fit in three stable pages")
