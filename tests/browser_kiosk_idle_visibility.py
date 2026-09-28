"""Kiosk destinations own the surface while the live shell is genuinely idle."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = ("plex", "nhl", "ufc", "pfl", "weather", "tv", "astronomy", "gaming", "calendar")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((393, 852), (430, 852), (700, 900), (1024, 600), (1500, 900)):
        for direct in (False, True):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(route):
                path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path in ("/kiosk", "/live"):
                    return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return route.fulfill(path=str(asset))
                if path == "/api/config":
                    return route.fulfill(json={"providers": {
                        key: {"enabled": True, "targets": ["kiosk"]} for key in DESTINATIONS
                    }, "fallback": {}})
                if path == "/contexts":
                    return route.fulfill(json={"contexts": [
                        {"id": f"{key}:fixture", "provider": key, "title": f"{key} fixture",
                         "starts": "2099-01-01T12:00:00Z"} for key in DESTINATIONS
                    ]})
                if path == "/providers":
                    return route.fulfill(json={"providers": {key: {"state": "ok"} for key in DESTINATIONS}})
                if path == "/now-playing.json":
                    return route.fulfill(json={"playing": False, "state": "idle", "availability": "idle"})
                if path in ("/settings.json", "/live-settings.json"):
                    return route.fulfill(json={"transitionMs": 0})
                if path == "/ambient.json":
                    return route.fulfill(json={"opacity": 0})
                return route.fulfill(json={})

            page.route("**/*", route)
            suffix = "?view=ufc" if direct else ""
            page.goto(f"http://marquee.test/kiosk{suffix}", wait_until="networkidle")
            page.wait_for_function("document.body.classList.contains('idle')")
            page.wait_for_selector('.kiosk-primary [data-view="ufc"][aria-current="page"]' if direct else '.kiosk-primary [data-view=""][aria-current="page"]')

            if not direct:
                ufc_link = page.locator('.kiosk-primary [data-view="ufc"]').first
                if not ufc_link.is_visible():
                    page.locator('.kiosk-more').click()
                    ufc_link = page.locator('.kiosk-menu [data-view="ufc"]').first
                ufc_link.click()
                page.wait_for_function("new URL(location.href).searchParams.get('view') === 'ufc'")

            for destination in DESTINATIONS:
                if page.url.split("view=")[-1].split("&")[0] != destination:
                    page.evaluate("destination => window.MarqueeNavigation.resolve({playing: false, state: 'idle'})", destination)
                    link = page.locator(f'.kiosk-primary [data-view="{destination}"], .kiosk-menu [data-view="{destination}"]').first
                    if not link.is_visible():
                        page.locator('.kiosk-more').click()
                        link = page.locator(f'.kiosk-menu [data-view="{destination}"]').first
                    link.click()
                # Re-enter the real shell state after each navigation; this is
                # the lifecycle edge that the deployed regression missed.
                page.evaluate("document.body.classList.add('idle')")
                if destination == "weather":
                    page.wait_for_function("document.querySelector('.stage')?.getClientRects().length === 1")
                    metrics = page.locator('.stage').evaluate("el => ({display: getComputedStyle(el).display, rect: el.getBoundingClientRect().toJSON(), section: 'weather'})")
                else:
                    page.wait_for_function("document.querySelector('.kiosk-section')?.getClientRects().length === 1")
                    metrics = page.locator('.kiosk-section').evaluate("el => ({display: getComputedStyle(el).display, rect: el.getBoundingClientRect().toJSON(), section: el.dataset.section})")
                assert metrics["display"] != "none" and metrics["rect"]["width"] > 0 and metrics["rect"]["height"] > 0, (width, direct, destination, metrics)
                assert page.locator('.brain-shell').evaluate("el => getComputedStyle(el).display") == "none"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (width, direct, destination)
                assert page.locator(f'.kiosk-rail [data-view="{destination}"][aria-current="page"], .kiosk-menu [data-view="{destination}"][aria-current="page"]').count() == 1, (width, direct, destination, page.url, page.locator('[aria-current="page"]').evaluate_all("els => els.map(el => el.dataset.view)"))

            page.locator('.kiosk-primary [data-view=""]').click()
            page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
            assert page.locator('.kiosk-section').evaluate("el => el.hidden")
            assert page.locator('.idle-screen').is_visible()
            assert not errors, errors
            page.close()
    browser.close()
    print("PASS: all kiosk destinations own visible nonzero surfaces during real idle at every required viewport")
