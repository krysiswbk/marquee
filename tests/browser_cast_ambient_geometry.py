"""Regression coverage for the Cast ambient calendar region swap."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def test_cast_ambient_swap_preserves_parent_sizing_and_computed_regions():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1024, 600), (1280, 800), (1500, 900)):
            page = browser.new_page(viewport={"width": width, "height": height})

            def route(route):
                path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                asset = ROOT / ("output" if path == "/image" else "output") / (
                    "index.html" if path == "/image" else path.lstrip("/")
                )
                if asset.is_file():
                    return route.fulfill(path=str(asset))
                return route.fulfill(json={})

            page.route("**/*", route)
            page.goto("http://marquee.test/image?context-demo=media", wait_until="domcontentloaded")
            result = page.evaluate(
                """
                () => {
                  const stage = document.querySelector('#stage');
                  const card = document.querySelector('#context-card');
                  stage.classList.remove('hidden');
                  stage.classList.add('contextual');
                  card.dataset.kind = 'ambient_agenda';
                  card.classList.remove('no-art');
                  card.style.display = 'grid';
                  document.body.classList.add('cast-display');
                  const rows = document.querySelector('#context-rows');
                  rows.hidden = false;
                  rows.replaceChildren(...Array.from({length: 5}, (_, i) => {
                    const item = document.createElement('span');
                    item.textContent = `Event ${i + 1}`;
                    return item;
                  }));
                  const style = selector => getComputedStyle(document.querySelector(selector));
                  const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
                  return {
                    clockSize: style('#context-clock').fontSize,
                    agendaSize: style('#context-rows').fontSize,
                    agendaMaxHeight: style('#context-rows').maxHeight,
                    agendaGap: style('#context-rows').columnGap,
                    source: {column: style('#context-source').gridColumnStart, row: style('#context-source').gridRowStart},
                    time: {column: style('#context-time').gridColumnStart, row: style('#context-time').gridRowStart},
                    agenda: {column: style('#context-rows').gridColumnStart, row: style('#context-rows').gridRowStart},
                    clockBox: box('#context-clock'),
                    agendaBox: box('#context-rows'),
                    cardBox: box('#context-card'),
                  };
                }
                """
            )
            # render() supplies the established 5.2vw context clock token;
            # the regression's 11vw Cast override must not return.
            expected_clock = width * 0.052
            expected_agenda = min(max(0.85 * 16, width * 0.0135), 1.4 * 16)
            assert abs(float(result["clockSize"].replace("px", "")) - expected_clock) < 0.1
            assert abs(float(result["agendaSize"].replace("px", "")) - expected_agenda) < 0.1
            assert result["agendaMaxHeight"] == f"{height * 0.28:g}px"
            assert result["agendaGap"] == f"{width * 0.02:g}px"
            assert result["source"] == {"column": "1", "row": "1"}
            assert result["agenda"] == {"column": "2", "row": "1"}
            assert result["time"] == {"column": "1", "row": "4"}
            assert result["agendaBox"]["left"] > result["cardBox"]["left"]
            assert result["clockBox"]["top"] > result["agendaBox"]["top"]
            page.close()
        browser.close()
