"""A Cast release poster stays decoded through repeated now-playing polls."""

import base64
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT = Path(__file__).resolve().parents[1] / "output"
ART = "data:image/svg+xml;base64," + base64.b64encode(
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><rect width="40" height="60" fill="red"/></svg>'
).decode()


def release(kind):
    return {
        "playing": True, "type": "media_context", "key": f"{kind}:fixture",
        "context": {"id": f"{kind}:fixture", "source": kind, "type": kind,
                    "title": "Release poster stability", "subtitle": "Coming soon",
                    "detail": "Release fixture", "artwork": ART},
    }


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for kind in ("movie_release", "tv_release"):
        page = browser.new_page(viewport={"width": 1024, "height": 600})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return request.fulfill(path=OUTPUT / "index.html", content_type="text/html")
            if path == "/now-playing.json":
                return request.fulfill(json=release(kind))
            if path in ("/settings.json", "/ambient.json", "/weather"):
                return request.fulfill(json={})
            asset = OUTPUT / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=asset)
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#context-art')?.naturalWidth === 40")
        page.evaluate("""() => {
          window.posterSourceChanges = 0;
          new MutationObserver(records => window.posterSourceChanges += records.length)
            .observe(document.querySelector('#context-art'),
                     {attributes:true,attributeFilter:['src']});
        }""")
        page.wait_for_timeout(6200)
        state = page.evaluate("""() => {
          const art = document.querySelector('#context-art');
          return {changes:window.posterSourceChanges, width:art.naturalWidth,
                  hidden:art.hidden, noArt:document.querySelector('#context-card').classList.contains('no-art')};
        }""")
        assert state == {"changes": 0, "width": 40, "hidden": False, "noArt": False}, (kind, state)
        assert not errors, (kind, errors)
        page.close()
    browser.close()
