"""Gaming context rows remain reachable, scrollable, and focus-safe."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = ((700, 900), (1024, 600), (1500, 900))


def assert_last_row_reachable(page) -> dict[str, int | float]:
    region = page.locator("#context-rows")
    metrics = page.evaluate(
        """() => {
          const region = document.querySelector('#context-rows');
          return {scrollHeight: region.scrollHeight, clientHeight: region.clientHeight,
            scrollTop: region.scrollTop};
        }"""
    )
    assert metrics["scrollHeight"] >= metrics["clientHeight"]
    region.focus()
    for _ in range(40):
        region.press("ArrowDown")
    page.wait_for_function("document.querySelector('#context-rows').scrollTop > 0")
    last = page.locator("#context-rows span").last
    box = last.bounding_box()
    region_box = region.bounding_box()
    assert box and region_box
    assert region_box["y"] <= box["y"]
    assert box["y"] + box["height"] <= region_box["y"] + region_box["height"] + 1
    assert last.is_visible()
    metrics["scrollTop"] = page.evaluate("document.querySelector('#context-rows').scrollTop")
    assert metrics["scrollTop"] > 0
    return metrics


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )

    for path in ("/live", "/kiosk"):
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            console_errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )

            def route_handler(route):
                request = route.request
                request_path = urlparse(request.url).path
                if request_path in ("/kiosk", "/live"):
                    return route.fulfill(
                        path=str(ROOT / "output/index.html"), content_type="text/html"
                    )
                if request_path == "/now-playing.json":
                    return route.fulfill(
                        json={
                            "playing": True,
                            "type": "media_context",
                            "key": "authoritative-gaming",
                            "context": {
                                "source": "gaming",
                                "type": "gaming",
                                "id": "gaming-authoritative",
                                "title": "Authoritative Gaming payload",
                                "subtitle": "Tonight · 8:00 PM",
                                "detail": "Stubbed provider payload",
                                "status": "UPCOMING",
                                "rows": ["Real queue item", "Real provider detail"],
                            },
                        }
                    )
                asset = ROOT / "output" / request_path.lstrip("/")
                if asset.is_file():
                    return route.fulfill(path=str(asset))
                if request_path == "/api/config":
                    return route.fulfill(json={"fallback": {}})
                if request_path in ("/settings.json", "/live-settings.json"):
                    return route.fulfill(json={"transitionMs": 0})
                if request_path == "/ambient.json":
                    return route.fulfill(json={"opacity": 0})
                if request_path == "/events":
                    return route.abort()
                return route.fulfill(json={})

            page.route("**/*", route_handler)
            page.goto(
                f"http://marquee.test{path}?demo=1&edit=1&context-demo=media-long",
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("#context-card[data-kind=gaming]")
            region = page.locator("#context-rows")
            assert region.get_attribute("role") == "region"
            assert region.get_attribute("aria-label") == "Context details"
            assert region.get_attribute("tabindex") == "0"
            assert region.locator("span").count() == 6

            more = page.locator("#context-rows-more")
            if more.is_visible():
                more.click()
                assert more.get_attribute("aria-expanded") == "true"
            metrics = assert_last_row_reachable(page)
            card = page.locator("#context-card").bounding_box()
            region_box = region.bounding_box()
            assert card and region_box
            assert card["y"] <= region_box["y"]
            assert region_box["y"] + region_box["height"] <= card["y"] + card["height"] + 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
            assert not console_errors, console_errors
            print(
                f"{path} {width}x{height}: rows "
                f"{metrics['scrollHeight']}/{metrics['clientHeight']}, last row reachable PASS"
            )
            page.close()

        page = browser.new_page(viewport={"width": 430, "height": 852}, is_mobile=True)
        page.route("**/*", route_handler)
        page.goto(
            f"http://marquee.test{path}?demo=1&edit=1&context-demo=media-long",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#context-card[data-kind=gaming]")
        more = page.locator("#context-rows-more")
        more.focus()
        more.press("Enter")
        assert more.get_attribute("aria-expanded") == "true"
        page.evaluate("window.postMessage({type:'marquee-cfg', cfg:{}}, location.origin)")
        page.wait_for_function(
            "document.querySelector('#context-rows-more').getAttribute('aria-expanded') === 'true'"
        )
        assert page.evaluate("document.activeElement.id === 'context-rows-more'")
        page.evaluate("window.postMessage({type:'marquee-demo-next'}, location.origin)")
        page.wait_for_function(
            "document.querySelector('#context-card').dataset.contextKey === 'gaming-alt'"
        )
        assert more.get_attribute("aria-expanded") == "false"
        assert page.evaluate("document.activeElement.id === 'context-rows-more'")
        page.evaluate("window.postMessage({type:'marquee-demo-context-reset'}, location.origin)")
        page.wait_for_function(
            "document.querySelector('#context-card').dataset.contextKey === 'calendar-preview'"
        )
        assert page.evaluate("document.activeElement.id === 'context-title'")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.close()
        print(f"{path} focus-preserving rerender and context changes PASS")

    page = browser.new_page(viewport={"width": 1024, "height": 600})
    page.route("**/*", route_handler)
    page.goto(
        "http://marquee.test/live?edit=1",
        wait_until="domcontentloaded",
    )
    page.wait_for_selector("#context-card[data-kind=gaming]", state="attached")
    assert page.locator("#context-card").get_attribute("data-context-key") == "gaming-authoritative"
    assert page.locator("#context-title").inner_text() == "Authoritative Gaming payload"
    page.evaluate("window.postMessage({type:'marquee-demo-context-reset'}, location.origin)")
    page.wait_for_function(
        "document.querySelector('#context-card').dataset.contextKey === 'gaming-authoritative'"
    )
    assert page.locator("#context-card").get_attribute("data-context-key") == "gaming-authoritative"
    assert page.locator("#context-title").inner_text() == "Authoritative Gaming payload"
    page.close()
    print("/live non-demo edit ignores demo context reset and preserves authoritative Gaming payload PASS")

    browser.close()
