"""Kiosk app updates refresh only its tab after household interaction settles."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text().strip()


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1500, "height": 971})
    health = {"version": VERSION}
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url) if frame == page.main_frame else None)
    page.add_init_script("""(() => {
      const interval = window.setInterval;
      window.setInterval = (callback, delay, ...args) => {
        if (delay === 300000) window.runKioskUpdateCheck = callback;
        return interval(callback, delay, ...args);
      };
    })()""")

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path == "/kiosk" and "receiver=1" in request.request.url:
            return request.fulfill(path=str(ROOT / "output/kiosk-receiver.html"), content_type="text/html")
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/healthz":
            return request.fulfill(json={"ok": True, "version": health["version"]})
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        return request.fulfill(json={})

    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk?wired=1", wait_until="domcontentloaded")
    page.wait_for_function("typeof window.runKioskUpdateCheck === 'function'")
    assert "wired=1" in page.locator("#brain-agenda-link").get_attribute("href")
    initial = len(navigations)
    page.evaluate("() => runKioskUpdateCheck()")
    assert len(navigations) == initial, "same release reloaded the kiosk"

    health["version"] = "new-release"
    page.evaluate("() => window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab'}))")
    page.evaluate("() => runKioskUpdateCheck()")
    assert len(navigations) == initial, "active household interaction was interrupted"
    page.evaluate("() => { const now = Date.now(); Date.now = () => now + 61000; }")
    with page.expect_event("framenavigated"):
        page.evaluate("() => runKioskUpdateCheck()")
    assert len(navigations) == initial + 1, "new release did not reload the kiosk"

    page.goto("http://marquee.test/live", wait_until="domcontentloaded")
    live = len(navigations)
    page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(100)
    assert len(navigations) == live, "live view was reloaded by kiosk updater"

    page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
    ordinary = len(navigations)
    page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(100)
    assert len(navigations) == ordinary, "unmarked Cast receiver document was reloaded"

    page.goto("http://marquee.test/kiosk?receiver=1&wired=1", wait_until="domcontentloaded")
    receiver = page.frame_locator("#kiosk")
    receiver.locator("body").wait_for()
    assert receiver.locator("body").evaluate("() => typeof window.runKioskUpdateCheck") == "undefined"

    page.goto("http://marquee.test/kiosk?demo=1", wait_until="domcontentloaded")
    demo = len(navigations)
    page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(100)
    assert len(navigations) == demo, "development fixture was reloaded"
    browser.close()
    print("PASS: kiosk-only release refresh leaves Live and development fixtures alone")
