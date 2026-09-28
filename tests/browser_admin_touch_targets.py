"""Browser contract for admin hit areas, numeric semantics, and narrow overflow."""

import os
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MARQUEE_SMOKE_URL", "http://127.0.0.1:18086")
ROUTES = [
    "/settings",
    "/settings/layout?profile=cast",
    "/settings/layout?profile=live",
    "/settings/attention",
    "/settings/tests",
]
VIEWPORTS = [(1500, 900), (1024, 600), (700, 900), (393, 852)]
TARGETS = (
    "button:not([hidden])",
    "summary:not([hidden])",
    "select:not([hidden])",
    "input[type=number]:not([hidden])",
    "input[type=range]:not([hidden])",
    ".workspace-nav a:not([hidden])",
    ".mq-profile-picker a:not([hidden])",
)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        for route in ROUTES:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(urljoin(BASE, route), wait_until="domcontentloaded")
            page.wait_for_timeout(500)
            for selector in TARGETS:
                for box in page.locator(selector).evaluate_all(
                    "els => els.filter(el => { const s=getComputedStyle(el); "
                    "return s.display !== 'none' && s.visibility !== 'hidden' && "
                    "el.getBoundingClientRect().width > 0; }).map(el => "
                    "({tag:el.tagName,id:el.id,rect:el.getBoundingClientRect().toJSON()}))"
                ):
                    assert box["rect"]["height"] >= 44, (width, height, route, selector, box)
            for control in page.locator('input[type="number"], input[type="range"]').evaluate_all(
                "els => els.filter(el => { const r=el.getBoundingClientRect(); "
                "return r.width > 0 && r.height > 0; }).map(el => ({id:el.id,min:el.min,max:el.max,step:el.step,described:el.getAttribute('aria-describedby')}))"
            ):
                assert control["min"] and control["max"] and control["step"], (route, control)
                assert control["described"], (route, control)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (width, height, route)
            if route != "/settings/layout?profile=live":
                dock = page.locator(".savebar").last
                if dock.count():
                    dock_box = dock.bounding_box()
                    if dock_box:
                        assert dock_box["y"] + dock_box["height"] <= height + 1, (width, height, route)
            assert not errors, (width, height, route, errors)
            page.close()
    print("PASS: admin targets, numeric semantics, overflow, dock reachability, and console errors across 5 routes × 4 viewports")
    browser.close()
