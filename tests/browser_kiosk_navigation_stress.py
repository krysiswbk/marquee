"""Repeated touch/remote navigation while kiosk resources and media rerender."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = ("plex", "nhl", "ufc", "pfl", "weather", "tv", "astronomy",
                "gaming", "calendar", "movies", "trailers", "major_events", "music")


def install_routes(page):
    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            return request.fulfill(json={"providers": {
                key: {"enabled": True, "targets": ["kiosk"]} for key in DESTINATIONS
            }, "fallback": {}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": [
                {"id": f"{key}:fixture", "provider": key,
                 "title": f"{key} fixture", "starts": "2099-01-01T12:00:00Z"}
                for key in DESTINATIONS if key != "plex"
            ]})
        if path == "/providers":
            return request.fulfill(json={"providers": {
                key: {"state": "ok"} for key in DESTINATIONS
            }})
        if path == "/now-playing.json":
            return request.fulfill(json={"playing": False, "state": "idle", "availability": "idle"})
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        return request.fulfill(json={})

    page.route("**/*", route)


def activate(page, destination, touch):
    direct = page.locator(f'.kiosk-primary a[data-view="{destination}"]')
    if not direct.is_visible():
        page.locator(".kiosk-more").click()
        target = page.locator(f'.kiosk-menu a[data-view="{destination}"]')
    else:
        target = direct
    if touch:
        target.tap()
    else:
        target.click()
    page.wait_for_function(
        "target => new URL(location.href).searchParams.get('view') === target",
        arg=destination,
    )
    page.wait_for_selector(f'[aria-current="page"][data-view="{destination}"]')
    assert page.locator(".kiosk-rail").evaluate(
        "el => [...el.querySelectorAll('a[data-view]')].some(a => a.offsetHeight >= 44)"
    )


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((390, 844), (1500, 1000)):
        context = browser.new_context(viewport={"width": width, "height": height}, has_touch=True)
        page = context.new_page()
        install_routes(page)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_selector('.kiosk-primary [data-view=""][aria-current="page"]')
        if width == 390:
            page.locator(".kiosk-more").click()
            settings = page.locator(".kiosk-menu details")
            settings.locator("summary").click()
            assert settings.evaluate("el => el.open")
            assert settings.locator("nav a").count() == 5
            assert all(settings.locator("nav a").nth(index).is_visible() for index in range(5))
            first_link = settings.locator("nav a").first.bounding_box()
            menu_box = page.locator(".kiosk-menu").bounding_box()
            assert first_link["y"] < menu_box["y"] + menu_box["height"] - 44, (first_link, menu_box)
            page.keyboard.press("Escape")
        for index in range(3):
            for destination in DESTINATIONS:
                # Start the same resource refresh that normally follows a
                # navigation, then activate during its render window.
                page.evaluate("window.MarqueeNavigation.refresh()")
                activate(page, destination, touch=index % 2 == 0)
                assert page.locator(
                    f'.kiosk-rail a[data-view="{destination}"][aria-current="page"], '
                    f'.kiosk-menu a[data-view="{destination}"][aria-current="page"]'
                ).count() == 1
                if page.locator(".kiosk-menu[open]").count():
                    page.keyboard.press("Escape")
            home = page.locator('.kiosk-primary a[data-view=""]')
            if not home.is_visible():
                page.locator(".kiosk-more").click()
                home = page.locator('.kiosk-menu a[data-view=""]')
            (home.tap() if index % 2 == 0 else home.click())
            page.wait_for_function("!new URL(location.href).searchParams.get('view')")
            assert page.locator('.kiosk-primary [data-view=""][aria-current="page"]').count() == 1
            assert page.locator(".kiosk-menu[open]").count() == 0
        context.close()
    browser.close()
    print("PASS: repeated touch/click destination activation survives refresh, overflow, and Home return")
