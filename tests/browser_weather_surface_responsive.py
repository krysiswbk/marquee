"""Deterministic contract for the dedicated weather surface hierarchy."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(320, 720), (360, 720), (393, 852), (430, 852),
             (700, 900), (1024, 600), (1500, 900)]


def route_for(route):
    path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
    if path in ("/live", "/kiosk"):
        return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
    asset = ROOT / "output" / path.lstrip("/")
    if asset.is_file():
        return route.fulfill(path=str(asset))
    if path in ("/settings.json", "/live-settings.json"):
        return route.fulfill(json={"transitionMs": 0})
    if path == "/ambient.json":
        return route.fulfill(json={"opacity": 0})
    return route.fulfill(json={})


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", route_for)
        page.goto(
            "http://marquee.test/kiosk?view=weather&demo=1&context-demo=weather-clear",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector(".stage.weather-context .wx-broadcast")
        page.wait_for_timeout(250)

        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator(".wx-broadcast").evaluate(
            "el => el.scrollWidth <= el.clientWidth"
        )
        assert page.locator(".wx-main").evaluate(
            "el => { const text = el.querySelector('.channel-outlook'); "
            "return !text || text.getBoundingClientRect().bottom <= "
            "el.getBoundingClientRect().bottom + 1; }"
        )
        assert page.locator(".wx-main").evaluate(
            "el => { const nav = el.parentElement.querySelector('.wx-segments'); "
            "return el.getBoundingClientRect().bottom <= nav.getBoundingClientRect().top + 1; }"
        )

        buttons = page.locator(".wx-segments button:not([hidden])")
        assert buttons.count() >= 2
        for index in range(buttons.count()):
            button = buttons.nth(index)
            assert button.evaluate(
                "el => el.offsetWidth >= 44 && el.offsetHeight >= 44"
            ), (width, height, index)
            button.scroll_into_view_if_needed()
            assert button.is_visible(), (width, height, index)

        page.screenshot(path=f"/tmp/marquee-2.10.65-weather-{width}x{height}.png")
        assert not errors, (width, height, errors)
        page.close()
    browser.close()

print("PASS: weather hierarchy has no clipping/overlap, horizontal overflow, or undersized controls across target viewports")
