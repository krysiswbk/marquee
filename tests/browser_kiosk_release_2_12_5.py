"""Browser contracts for the 2.12.5 reliability and focus fixes."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def install_routes(page, delayed_config=False):
    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            if delayed_config:
                return request.abort("timedout")
            return request.fulfill(json={"providers": {"weather": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": [{
                "id": "weather:contract", "source": "weather", "provider": "weather",
                "type": "weather", "subtype": "current", "title": "Weather at home",
                "weather": {"current": {"temperature_2m": 21, "apparent_temperature": 21,
                "relative_humidity_2m": 45, "wind_speed_10m": 8, "weather_code": 0, "is_day": 1},
                "hours": [], "days": []},
            }]})
        if path == "/providers":
            return request.fulfill(json={"providers": {"weather": {"state": "ok"}}})
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        return request.fulfill(json={})

    page.route("**/*", route)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )

    page = browser.new_page(viewport={"width": 1024, "height": 600})
    install_routes(page, delayed_config=True)
    page.goto("http://marquee.test/kiosk?view=calendar", wait_until="domcontentloaded")
    assert page.locator('.kiosk-primary a[data-view=""]').count() == 1
    assert page.locator('.kiosk-primary a[data-view="weather"]').count() == 1
    assert page.locator('.kiosk-primary a[data-view="calendar"]').count() == 1
    assert page.locator('.kiosk-primary a[data-view="calendar"][aria-current="page"]').count() == 1
    page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
    install_routes(page)
    page.goto("http://marquee.test/kiosk?view=weather", wait_until="domcontentloaded")
    heading = page.locator("#wx-segment-title")
    heading.wait_for(state="visible")
    page.wait_for_function("document.activeElement?.id === 'wx-segment-title'")
    assert page.evaluate("""() => {
        const style = getComputedStyle(document.activeElement);
        return style.outlineStyle === 'none' &&
               style.textDecorationLine.includes('underline') &&
               style.animationName === 'none';
    }""")
    assert page.locator('.kiosk-primary a[data-view="weather"][aria-current="page"]').count() == 1
    page.close()
    browser.close()
    print("PASS: cold direct-load rail topology and reduced-motion Weather heading focus")
