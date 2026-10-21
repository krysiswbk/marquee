"""Kiosk app updates refresh wired tabs and HA popups after interaction settles."""

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
        if request.request.url.startswith("http://ha.test/dashboard"):
            return request.fulfill(
                body='<iframe name="marquee-popup" src="http://marquee.test/kiosk"></iframe>',
                content_type="text/html",
            )
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

    popup_page = browser.new_page()
    popup_page.add_init_script("""(() => {
      const interval = window.setInterval;
      window.setInterval = (callback, delay, ...args) => {
        if (delay === 300000) window.runKioskUpdateCheck = callback;
        return interval(callback, delay, ...args);
      };
    })()""")
    popup_page.route("**/*", route)
    popup_navigations = []
    popup_page.on("framenavigated", lambda frame: popup_navigations.append(frame.url))
    health["version"] = VERSION
    popup_page.goto("http://ha.test/dashboard", wait_until="domcontentloaded")
    popup_page.frame_locator('iframe[name="marquee-popup"]').locator("body").wait_for()
    popup_frame = popup_page.frame(name="marquee-popup")
    popup_frame.wait_for_function("typeof window.runKioskUpdateCheck === 'function'")
    assert popup_frame.url == "http://marquee.test/kiosk"
    popup_initial = len(popup_navigations)
    popup_frame.evaluate("() => runKioskUpdateCheck()")
    assert len(popup_navigations) == popup_initial, "same release reloaded the HA popup"

    health["version"] = "next-release"
    popup_frame.evaluate("() => window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab'}))")
    popup_frame.evaluate("() => runKioskUpdateCheck()")
    assert len(popup_navigations) == popup_initial, "active HA popup interaction was interrupted"
    popup_frame.evaluate("() => { const now = Date.now(); Date.now = () => now + 61000; }")
    with popup_page.expect_event("framenavigated", predicate=lambda frame: frame == popup_frame):
        popup_frame.evaluate("() => runKioskUpdateCheck()")
    assert popup_page.url == "http://ha.test/dashboard", "HA parent navigated during popup update"
    assert len(popup_navigations) == popup_initial + 1, "new release did not reload the HA popup"
    for excluded_url in ("/live", "/kiosk?demo=1", "/kiosk?edit=1"):
        popup_frame.goto(f"http://marquee.test{excluded_url}", wait_until="domcontentloaded")
        assert popup_frame.evaluate("() => typeof window.runKioskUpdateCheck") == "undefined", (
            f"updater activated in excluded HA popup view: {excluded_url}"
        )
    popup_page.close()

    page.goto("http://marquee.test/kiosk?demo=1", wait_until="domcontentloaded")
    demo = len(navigations)
    page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(100)
    assert len(navigations) == demo, "development fixture was reloaded"
    browser.close()
    print("PASS: wired and HA popup refresh leaves Cast, Live and development fixtures alone")
