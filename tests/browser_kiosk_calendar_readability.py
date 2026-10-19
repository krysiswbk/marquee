"""Calendar text and synth palette at the short wall-tablet viewport."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
EVENTS = [
    {"id": "calendar:waste", "provider": "calendar", "type": "calendar_event",
     "subtype": "all_day", "title": "Garbage, blue box, green cart, bulk waste (3 items max), and yard waste",
     "subtitle": "Today", "detail": "Garbage, blue box, green cart, bulk waste (3 items max), and yard waste",
     "rows": ["Garbage"], "starts": "2099-10-19T04:00:00Z", "expires": "2099-10-20T04:00:00Z"},
    {"id": "calendar:moon", "provider": "calendar", "type": "calendar_event",
     "subtype": "timed", "title": "Full Moon", "subtitle": "Sun, Oct 25 · 8:00 PM",
     "rows": ["Household calendar"], "starts": "2099-10-25T20:00:00Z", "expires": "2099-10-25T21:00:00Z"},
    {"id": "calendar:blue", "provider": "calendar", "type": "calendar_event",
     "subtype": "all_day", "title": "Blue box and green cart", "subtitle": "Mon, Oct 26",
     "rows": ["Garbage"], "starts": "2099-10-26T04:00:00Z", "expires": "2099-10-27T04:00:00Z"},
    {"id": "calendar:birthday", "provider": "calendar", "type": "calendar_event",
     "subtype": "all_day", "title": "Birthday", "subtitle": "Thu, Oct 29",
     "rows": ["Birthday"], "starts": "2099-10-29T04:00:00Z", "expires": "2099-10-30T04:00:00Z"},
]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1024, "height": 600})

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/config":
            return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": EVENTS})
        if path == "/providers":
            return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        asset = ROOT / "output" / path.lstrip("/")
        return request.fulfill(path=str(asset)) if asset.is_file() else request.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    page.wait_for_selector(".kiosk-agenda-feature")
    evidence = page.evaluate("""() => {
      const panel = document.querySelector('.kiosk-section[data-section=calendar]');
      const feature = panel.querySelector('.kiosk-agenda-feature');
      const row = panel.querySelector('.kiosk-agenda-row');
      return {
        theme: document.documentElement.dataset.kioskTheme,
        background: getComputedStyle(panel).backgroundImage,
        featureBackground: getComputedStyle(feature).backgroundImage,
        titleSize: parseFloat(getComputedStyle(feature.querySelector('h2')).fontSize),
        eventSize: parseFloat(getComputedStyle(row.querySelector('strong')).fontSize),
        source: feature.querySelector('.kiosk-meta').textContent,
        title: feature.querySelector('h2').textContent,
        contentBottom: panel.querySelector('.kiosk-agenda').getBoundingClientRect().bottom,
        panelBottom: panel.getBoundingClientRect().bottom,
      };
    }""")
    assert evidence["theme"] == "synthwave", evidence
    assert "255, 79, 200" in evidence["background"] and "255, 79, 200" in evidence["featureBackground"], evidence
    assert evidence["titleSize"] >= 30 and evidence["eventSize"] >= 19, evidence
    assert evidence["source"] == "Garbage" and evidence["source"] != evidence["title"], evidence
    assert evidence["contentBottom"] <= evidence["panelBottom"], evidence
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), evidence
    page.locator("[data-calendar-disclosure]").click()
    assert page.locator(".kiosk-calendar-page .kiosk-agenda-row strong").first.evaluate(
        "el => parseFloat(getComputedStyle(el).fontSize) >= 19"
    )
    browser.close()
    print(f"PASS: tablet Calendar uses synth colors, readable event text, concise feature, and contained layout: {evidence}")
