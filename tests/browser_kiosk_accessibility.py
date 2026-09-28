"""Browser regression checks for kiosk destination semantics and focus lifecycle."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1024, "height": 600})

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            data = {"providers": {"gaming": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}}
        elif path == "/contexts":
            data = {
                "contexts": [
                    {"id": "gaming:one", "provider": "gaming", "title": "Lead game", "starts": "2099-01-01T12:00:00Z"},
                    {"id": "gaming:two", "provider": "gaming", "title": "Queue game", "starts": "2099-01-01T13:00:00Z"},
                ]
            }
        elif path == "/providers":
            data = {"providers": {"gaming": {"state": "ok"}}}
        elif path in ("/settings.json", "/live-settings.json"):
            data = {"transitionMs": 0}
        elif path == "/ambient.json":
            data = {"opacity": 0}
        else:
            data = {}
        return request.fulfill(body=json.dumps(data), content_type="application/json")

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-primary [data-view="gaming"]')

    # Home starts exposed and usable.
    assert page.locator(".stage").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden')")

    page.locator('.kiosk-primary [data-view="gaming"]').click()
    page.wait_for_function("document.querySelector('.kiosk-section:not([hidden])') !== null")
    assert page.locator(".stage").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")
    assert page.locator(".idle-screen").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")
    assert page.locator(".kiosk-rail").evaluate("el => !el.inert")
    assert page.locator(".kiosk-section").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden')")

    page.locator('.kiosk-primary [data-view=""]').click()
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.evaluate("document.activeElement?.dataset.view") == ""

    page.locator('.kiosk-primary [data-view="gaming"]').click()
    page.keyboard.press("Escape")
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.locator(".stage").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden')")
    assert page.evaluate("document.activeElement?.dataset.view") == ""

    page.locator('.kiosk-primary [data-view="gaming"]').click()
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.evaluate("document.activeElement?.dataset.view") == ""
    assert page.locator(".kiosk-section").evaluate("el => el.hidden && el.inert && el.getAttribute('aria-hidden') === 'true'")

    page.goto("http://marquee.test/kiosk?audit=2.10.50&view=gaming", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('.kiosk-section:not([hidden])') !== null")
    assert page.locator(".stage").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.locator(".stage").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden')")

    browser.close()
    print("PASS: active destination owns background semantics; Escape, Home, and browser back restore dashboard and Home focus")
