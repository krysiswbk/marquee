"""Cast media and sports readability/containment at receiver sizes."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1] / "output"
CASES = (("sports-demo=1", ".sports-card", ".sport-matchup"),
         ("context-demo=media", ".context-card", ".context-copy"),
         ("context-demo=media-long", ".context-card", ".context-copy"))


def test_cast_calendar_and_plex_are_separate_scenes():
    calendar = {"playing": True, "type": "media_context", "key": "calendar:agenda",
                "context": {"source": "calendar", "type": "calendar_event",
                            "subtype": "ambient_agenda", "title": "Recycling pickup",
                            "subtitle": "Today", "rows": [{"when": "Tomorrow", "title": "Birthday"}]}}
    plex = {"playing": True, "type": "episode", "key": "plex:episode",
            "title": "Scariest House in America", "subtitle": "S3 · E4",
            "progress": {"offsetMs": 600000, "durationMs": 2400000}}
    current = {"payload": calendar}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1024, "height": 600})

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
            if path == "/now-playing.json":
                return request.fulfill(json=current["payload"])
            if path == "/settings.json":
                return request.fulfill(json={"theme": "synthwave", "template": "bigclock"})
            asset = ROOT / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#stage').classList.contains('contextual')")
        assert page.locator(".b-identity").evaluate("el => getComputedStyle(el).display") == "none"
        current["payload"] = plex
        page.evaluate("window.MarqueeLifecycle.request('now-playing')")
        page.wait_for_function("document.querySelector('#stage').classList.contains('cast-media')")
        assert page.locator("#context-card").evaluate("el => getComputedStyle(el).display") == "none"
        assert page.locator("#title").inner_text() == plex["title"]
        assert page.locator(".b-progress").evaluate("el => getComputedStyle(el).display") != "none"
        page.close()
        browser.close()


def test_cast_idle_uses_saved_synth_theme():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1024, "height": 600})

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
            asset = ROOT / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            if path == "/settings.json":
                return request.fulfill(json={"theme": "synthwave", "accent": "#2675df"})
            return request.fulfill(json={"playing": False})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_function("document.documentElement.dataset.theme === 'synthwave'")
        assert page.locator("body").evaluate("el => el.classList.contains('idle')")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#ff4fc8"
        page.evaluate("document.body.classList.add('sky-day')")
        assert page.locator("#idle-weather-temp").evaluate(
            "el => getComputedStyle(el).color") == "rgb(255, 240, 251)"
        page.close()
        browser.close()


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        for width, height in ((1024, 600), (1280, 800), (800, 480)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/image":
                    return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
                asset = ROOT / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                if path == "/settings.json":
                    return request.fulfill(json={"theme": "synthwave"})
                if path == "/weather.json":
                    return request.fulfill(json={})
                return request.fulfill(status=404)

            page.route("**/*", route)
            for query, scene, content in CASES:
                page.goto(f"http://marquee.test/image?demo=1&edit=1&{query}", wait_until="domcontentloaded")
                page.wait_for_selector(f".stage{'.sports' if 'sports' in query else '.contextual'} {scene}")
                assert page.locator('link[href*="cast-media-sports.css"]').count() == 1
                details = page.evaluate("""({scene, content}) => {
                    const card = document.querySelector(scene), child = document.querySelector(content);
                    const c = card.getBoundingClientRect(), d = child.getBoundingClientRect();
                    const css = getComputedStyle(card);
                    return {card: c.toJSON(), content: d.toJSON(), background: css.backgroundImage,
                        overflow: card.scrollHeight > card.clientHeight + 1,
                        childContained: d.top >= c.top && d.bottom <= c.bottom + 1};
                }""", {"scene": scene, "content": content})
                assert not details["overflow"], (width, height, query, details)
                assert details["childContained"], (width, height, query, details)
                assert "16, 11, 34" in details["background"] or "33, 18, 61" in details["background"], details
                if "sports" in query:
                    assert page.locator(".sport-record").first.evaluate(
                        "el => parseFloat(getComputedStyle(el).fontSize)") >= 14
                    assert page.locator(".sport-league-logo").evaluate(
                        "el => getComputedStyle(el).display") == "none"
                else:
                    assert page.locator(".context-detail").evaluate(
                        "el => parseFloat(getComputedStyle(el).fontSize)") >= 17
                    assert page.locator(".context-rows").evaluate(
                        "el => el.scrollWidth <= el.clientWidth + 1"), query
                page.screenshot(path=f"/tmp/marquee-cast-{query.split('=')[0]}-{width}x{height}.png")
            assert not errors, errors
            page.close()
        browser.close()
    print("PASS: cast sports/media synth backgrounds and contained primary content at 1024x600, 1280x800, 800x480")


if __name__ == "__main__":
    run()
