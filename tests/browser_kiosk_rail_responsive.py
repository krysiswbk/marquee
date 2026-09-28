"""Responsive active-destination identity and direct-rail behavior."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(360, 800), (393, 852), (430, 932), (700, 900),
             (1024, 600), (1500, 900), (1280, 480)]
DESTINATIONS = ("plex", "nhl", "ufc", "pfl", "weather", "tv", "astronomy", "gaming", "calendar")
TEST_DESTINATIONS = DESTINATIONS
LABELS = {"plex": "Now playing", "nhl": "NHL", "ufc": "UFC", "pfl": "PFL",
          "weather": "Weather", "tv": "TV", "astronomy": "Sky", "gaming": "Gaming",
          "calendar": "Calendar"}


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        for destination in TEST_DESTINATIONS:
            page = browser.new_page(viewport={"width": width, "height": height})

            def route(route):
                path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path in ("/kiosk", "/live"):
                    return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return route.fulfill(path=str(asset))
                if path == "/api/config":
                    return route.fulfill(json={
                        "providers": {key: {"enabled": True, "targets": ["kiosk"]}
                                      for key in (*DESTINATIONS, "plex")},
                        "fallback": {},
                    })
                if path == "/contexts":
                    return route.fulfill(json={"contexts": [
                        {"id": f"{key}:one", "provider": key, "title": f"{key.upper()} fixture",
                         "starts": "2099-01-01T12:00:00Z"}
                        for key in DESTINATIONS
                    ]})
                if path == "/providers":
                    return route.fulfill(json={"providers": {
                        **{key: {"state": "ok"} for key in DESTINATIONS},
                        "plex": {"state": "ok", "contexts": [{"playing": True, "title": "Fixture"}]},
                    }})
                if path in ("/settings.json", "/live-settings.json"):
                    return route.fulfill(json={"transitionMs": 0})
                if path == "/ambient.json":
                    return route.fulfill(json={"opacity": 0})
                return route.fulfill(json={})

            page.route("**/*", route)
            page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
            page.wait_for_selector('.kiosk-primary [data-view=""][aria-current="page"]')
            assert page.locator('[aria-current="page"]').count() == 1, (width, "home")
            assert page.locator('.kiosk-more[aria-current]').count() == 0
            assert page.locator('.kiosk-menu a[href="/live"][aria-current]').count() == 0
            assert page.evaluate("new URL(location.href).searchParams.get('view') === null")
            assert page.locator('.kiosk-primary a[data-view]').evaluate_all(
                "els => { const marks = els.map(el => el.querySelector('svg')?.innerHTML); "
                "return marks.length === new Set(marks).size && marks.every(Boolean); }"
            )

            page.goto(f"http://marquee.test/kiosk?view={destination}", wait_until="domcontentloaded")
            page.wait_for_selector(f'.kiosk-primary [data-view="{destination}"][aria-current="page"]')

            assert page.locator('[aria-current="page"]').count() == 1, (width, destination)
            assert page.locator('.kiosk-more[aria-current]').count() == 0
            assert page.locator('.kiosk-menu a[href="/live"][aria-current]').count() == 0

            active = page.locator(f'.kiosk-primary [data-view="{destination}"]')
            assert active.locator(".kiosk-label").is_visible(), (width, destination)
            assert active.locator(".kiosk-label").inner_text() == LABELS[destination]
            assert active.evaluate("el => el.offsetHeight >= 44 && el.getBoundingClientRect().width >= 44")
            assert active.locator(".kiosk-label").evaluate(
                "el => el.getClientRects().length === 1 && el.offsetHeight < 30")
            assert page.locator('.kiosk-primary [data-view=""]').count() == 1
            assert page.locator(".kiosk-rail").evaluate(
                "el => el.scrollWidth <= el.clientWidth + 1")
            assert page.locator(".kiosk-primary").evaluate(
                "el => [...el.querySelectorAll('a:not([hidden])')].every(a => a.offsetHeight >= 44)")

            destination_links = page.locator(
                f'.kiosk-primary [data-view="{destination}"], .kiosk-menu [data-view="{destination}"]'
            )
            assert destination_links.first.locator(".kiosk-icon svg").count() == 1
            assert destination_links.first.locator(".kiosk-icon").get_attribute("aria-hidden") == "true"
            assert destination_links.first.get_attribute("aria-label") == LABELS[destination]
            assert destination_links.first.locator(".kiosk-icon svg").evaluate(
                "el => getComputedStyle(el).stroke === 'currentColor' || getComputedStyle(el).stroke !== 'none'"
            )

            if width <= 430:
                assert page.locator(".kiosk-more").evaluate(
                    "el => !el.hidden && el.getBoundingClientRect().width >= 44")
                page.locator(".kiosk-more").press("Enter")
                page.wait_for_function("document.querySelector('.kiosk-menu[open]') !== null")
                assert page.locator('.kiosk-primary [data-view=""]').count() == 1
                assert page.locator('.kiosk-menu [data-view=""]').count() == 0
                assert page.locator('[aria-current="page"]').count() == 1
                assert page.locator('.kiosk-more[aria-current]').count() == 0
                assert page.locator('.kiosk-menu a[href="/live"][aria-current]').count() == 0
                page.keyboard.press("Escape")
                page.wait_for_function("document.querySelector('.kiosk-menu[open]') === null")

            home = page.locator('.kiosk-primary [data-view=""]')
            home.focus()
            home.press("Enter")
            page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
            assert page.locator('.kiosk-primary [data-view=""][aria-current="page"]').count() == 1
            assert page.locator('[aria-current="page"]').count() == 1
            assert page.locator('.kiosk-more[aria-current]').count() == 0
            assert page.locator('.kiosk-menu a[href="/live"][aria-current]').count() == 0
            assert page.evaluate("document.activeElement?.dataset.view === ''")
            page.close()
    browser.close()
    print("PASS: active labels, fit, Home, More, focus, and return-to-dashboard hold across rail widths")
