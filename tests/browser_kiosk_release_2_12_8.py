"""Rapid kiosk replacement regression: no transparent stage between frames."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def payload(index):
    return {
        "playing": True,
        "type": "media_context",
        "key": f"fixture-{index}",
        "context": {
            "source": "calendar",
            "type": "calendar_event",
            "title": f"Frame {index}",
            "subtitle": "Replacement is ready",
            "detail": "The previous frame remains painted until this frame is committed.",
        },
    }


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((390, 844), (700, 900), (1024, 600), (1500, 900)):
        page = browser.new_page(viewport={"width": width, "height": height}, reduced_motion="no-preference")
        state = {"index": 0}

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/kiosk", "/live"):
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            if path == "/api/config":
                return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
            if path == "/now-playing.json":
                state["index"] += 1
                return request.fulfill(json=payload(state["index"]))
            if path in ("/settings.json", "/live-settings.json"):
                return request.fulfill(json={"transitionMs": 5000})
            if path == "/ambient.json":
                return request.fulfill(json={"opacity": 0})
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk?view=plex", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('.stage')?.classList.contains('contextual')")
        assert page.locator("#context-title").inner_text().startswith("Frame")

        for _ in range(8):
            page.evaluate("window.MarqueeLifecycle.request('now-playing')")
            page.wait_for_function("document.querySelector('#context-title')?.textContent.includes('Frame')")
            snapshot = page.evaluate("""() => {
                const stage = document.querySelector('.stage');
                const title = document.querySelector('#context-title');
                const rect = title?.getBoundingClientRect();
                return {opacity: getComputedStyle(stage).opacity, visible: rect?.width > 0 && rect?.height > 0,
                    title: title?.textContent};
            }""")
            assert snapshot["opacity"] != "0", snapshot
            assert snapshot["visible"], snapshot
            assert page.locator("#context-title").bounding_box()["width"] > 0
        page.close()
    browser.close()
    print("PASS: repeated replacement cycles keep the committed stage painted and touch-visible")
