"""The physical kiosk rotates its feed; Cast kiosk receivers hold one item."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


root = Path(__file__).resolve().parents[1]
brain = {"fresh": True, "openings": [], "events": [], "cards": [], "alerts": [],
         "people": [], "unknown": [], "garage_occupied": True, "network": "online"}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    for suffix, rotates in (("", True), ("?display=hubs", False),
                            ("?display=garage", False)):
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/kiosk":
                return request.fulfill(path=str(root / "output/index.html"), content_type="text/html")
            if path == "/api/brain":
                return request.fulfill(json=brain)
            if path in ("/api/config", "/settings.json", "/live-settings.json"):
                return request.fulfill(json={"providers": {}, "fallback": {"screen": "clock_weather"}})
            asset = root / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto(f"http://marquee.test/kiosk{suffix}", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#brain-dock-copy')?.dataset.fullText")
        first = page.locator("#brain-dock-copy").get_attribute("data-full-text")
        page.evaluate("""() => {
          const original = Date.now;
          Date.now = () => original() + 12000;
          window.MarqueeBrain.configure({}, {screen:'clock_weather'});
        }""")
        second = page.locator("#brain-dock-copy").get_attribute("data-full-text")
        assert (first != second) is rotates, (suffix, first, second)
        assert not errors, errors
        page.close()
    browser.close()

print("PASS: kiosk feed rotates while Hub and garage Cast receivers stay still")
