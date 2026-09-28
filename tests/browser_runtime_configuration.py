"""Read-only deployed configuration-surface acceptance checks."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = os.environ.get("MARQUEE_BASE_URL", "http://10.10.9.37:8084").rstrip("/")
EVIDENCE = Path(os.environ.get("MARQUEE_EVIDENCE_DIR", "/tmp/marquee-2.10.54-evidence"))
VIEWPORTS = [(1500, 900), (1024, 600), (700, 900), (393, 852)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"),
        args=["--no-sandbox"],
    )
    for route, name in (("/settings", "settings"),
                        ("/settings/layout?profile=cast", "cast"),
                        ("/settings/layout?profile=live", "live")):
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            failed = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("requestfailed", lambda request: failed.append(request.url))
            page.goto(BASE + route, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1200)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (name, width, height)
            if name == "settings":
                page.locator("#app").wait_for()
                mobile = page.locator("#mobile-actionbar")
                if width <= 520:
                    assert mobile.is_visible()
                    assert page.locator("#mobile-save").is_disabled()
                    assert page.locator("#mobile-discard").is_disabled()
                    page.locator("#tab-content").click()
                    assert page.locator("#tab-content").get_attribute("aria-selected") == "true"
                    page.locator("#tab-displays").click()
                    assert page.locator("#tab-displays").get_attribute("aria-selected") == "true"
                    scroll_height = page.evaluate("document.documentElement.scrollHeight")
                    for position_name, position in (("top", 0),
                                                     ("mid", scroll_height // 2),
                                                     ("bottom", scroll_height)):
                        page.evaluate("position => scrollTo(0, position)", position)
                        page.wait_for_timeout(100)
                        dock = mobile.bounding_box()
                        assert dock and dock["y"] >= -1 and dock["y"] + dock["height"] <= height + 1, (
                            name, width, height, position_name, dock
                        )
                else:
                    assert not mobile.is_visible()
            else:
                assert page.locator("#save").is_disabled()
                assert page.locator("#discard").is_disabled()
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(EVIDENCE / f"{name}-{width}x{height}.png"), full_page=True)
            assert not errors, (name, width, height, errors)
            assert not failed, (name, width, height, failed)
            print(f"{name} {width}x{height}: pristine actions, bounds, console/network PASS")
            page.close()
    browser.close()
