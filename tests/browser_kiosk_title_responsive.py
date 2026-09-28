"""Deterministic responsive long-title coverage for kiosk browse destinations."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(393, 852), (700, 900), (1024, 600), (1500, 900)]
DESTINATIONS = ("gaming", "tv", "movies", "trailers")
LONG_TITLE = "Minecraft Dungeons II (PS5/Xbox/Switch/PC)"


def fixture_contexts():
    return [
        {"id": f"{provider}:lead", "provider": provider, "title": LONG_TITLE,
         "subtitle": "Available now", "starts": "2099-01-01T12:00:00Z"}
        for provider in DESTINATIONS
    ] + [
        {"id": "gaming:queue", "provider": "gaming",
         "title": "The Legend of Zelda: Tears of the Kingdom — Collector's Edition",
         "subtitle": "Up next", "starts": "2099-01-01T13:00:00Z"},
        {"id": "tv:queue", "provider": "tv",
         "title": "The Lord of the Rings: The Rings of Power",
         "subtitle": "Later", "starts": "2099-01-01T14:00:00Z"},
    ]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        for destination in DESTINATIONS:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(route):
                request = route.request
                path = request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
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
                    return route.fulfill(json={"contexts": fixture_contexts()})
                if path == "/providers":
                    return route.fulfill(json={"providers": {key: {"state": "ok"} for key in DESTINATIONS}})
                if path == "/now-playing.json":
                    return route.fulfill(json={"playing": False})
                if path in ("/settings.json", "/live-settings.json"):
                    return route.fulfill(json={"transitionMs": 0})
                if path == "/ambient.json":
                    return route.fulfill(json={"opacity": 0})
                return route.fulfill(json={})

            page.route("**/*", route)
            page.goto(f"http://marquee.test/kiosk?view={destination}", wait_until="domcontentloaded")
            page.wait_for_selector(".kiosk-editorial-feature h2")
            assert page.locator(".kiosk-editorial-feature h2").inner_text() == LONG_TITLE
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

            fragments = page.locator(".kiosk-editorial-feature h2").evaluate("""node => {
                const textNodes = [];
                const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
                while (walker.nextNode()) textNodes.push(walker.currentNode);
                return textNodes.flatMap(text => [...text.data.matchAll(/[A-Za-z0-9]+/g)].map(match => {
                    const range = document.createRange();
                    range.setStart(text, match.index);
                    range.setEnd(text, match.index + match[0].length);
                    return {word: match[0], rects: [...range.getClientRects()].length};
                }));
            }""")
            assert all(item["rects"] == 1 for item in fragments), (width, height, destination, fragments)
            assert page.locator('.kiosk-primary [data-view=""]').count() == 1
            assert page.locator('.kiosk-primary [data-view=""]').evaluate("el => el.getAttribute('aria-label') === 'Home'")
            assert not errors, (width, height, destination, errors)
            page.close()
    browser.close()
    print("PASS: long browse titles preserve whole words, slash opportunities, no overflow, Home reachability, and console health")
