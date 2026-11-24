"""Calendar uses tall screens for more real events without covering the dock."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVENTS = [{"id": "calendar:birthdays", "provider": "calendar", "type": "calendar_event",
           "subtype": "birthday_rollup", "title": "Casey's birthday", "subtitle": "Today",
           "rows": ["Jordan · In 6 days", "Sam · In 12 days", "Lee · In 20 days"],
           "starts": "2099-10-01T00:00:00Z", "expires": "2099-10-02T00:00:00Z"}]
EVENTS += [{"id": f"calendar:{n}", "provider": "calendar", "type": "calendar_event",
            "title": f"Event {n}", "subtitle": f"In {n} days",
            "starts": f"2099-10-{n + 1:02d}T19:00:00Z",
            "expires": f"2099-10-{n + 1:02d}T20:00:00Z"} for n in range(1, 8)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    for width, height, expected in ((1500, 1000, 4), (1280, 800, 3), (3000, 2000, 7)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/kiosk", "/live"):
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/config":
                return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}})
            if path == "/contexts":
                return request.fulfill(json={"contexts": EVENTS})
            if path == "/providers":
                return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
            asset = ROOT / "output" / path.lstrip("/")
            return request.fulfill(path=str(asset)) if asset.is_file() else request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-agenda-feature")
        assert page.locator(".kiosk-agenda-groups .kiosk-agenda-row").count() == expected
        extra = page.locator(".kiosk-agenda-feature-next")
        assert extra.is_visible() == (height >= 850)
        if height >= 850:
            assert "Jordan" in extra.inner_text() and "Sam" in extra.inner_text()
            assert "Jordan" not in page.locator(".kiosk-agenda-feature .kiosk-meta").inner_text()
        assert page.evaluate("""() => {
            const panel = document.querySelector('.kiosk-section[data-section=calendar]');
            return panel.querySelector('.kiosk-agenda').getBoundingClientRect().bottom
              <= panel.getBoundingClientRect().bottom + 1;
        }""")
        assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")
        assert not errors, errors
        page.close()
    EVENTS[:] = [{"id": f"calendar:long-{n}", "provider": "calendar", "type": "calendar_event",
                  "title": "Long household event with every important detail in the title " * 3 + str(n),
                  "subtitle": "Tomorrow 7pm", "starts": f"2099-11-{n + 1:02d}T19:00:00Z",
                  "expires": f"2099-11-{n + 1:02d}T20:00:00Z"} for n in range(8)]
    long_page = browser.new_page(viewport={"width": 1500, "height": 1000})
    long_page.route("**/*", route)
    long_page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    long_page.wait_for_selector(".kiosk-agenda-feature")
    assert long_page.locator(".kiosk-agenda-groups .kiosk-agenda-row").count() == 4
    assert long_page.evaluate("""() => {
        const panel = document.querySelector('.kiosk-section[data-section=calendar]');
        return panel.querySelector('.kiosk-agenda').getBoundingClientRect().bottom
          <= panel.getBoundingClientRect().bottom + 1;
    }""")
    assert long_page.locator("[data-calendar-disclosure]").is_visible()
    long_page.close()
    browser.close()
    print("PASS: Calendar reveals more events and birthday context on tall screens without overflow")
