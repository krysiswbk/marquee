"""Rendered Nest Hub regression coverage for the Cast calendar composition."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
KINDS = ("calendar_event", "ambient_agenda")


def _route(route):
    path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
    asset = ROOT / "output" / ("index.html" if path == "/image" else path.lstrip("/"))
    if asset.is_file():
        return route.fulfill(path=str(asset))
    return route.fulfill(json={})


def _exercise(page, kind, row_count, weather_text=""):
    page.goto("http://marquee.test/image?context-demo=media", wait_until="domcontentloaded")
    return page.evaluate(
        """
        ({kind, rowCount, weatherText}) => {
          const stage = document.querySelector('#stage');
          const card = document.querySelector('#context-card');
          document.body.classList.remove('idle');
          stage.classList.remove('hidden', 'fade');
          document.querySelector('.idle-screen').style.display = 'none';
          stage.classList.add('contextual');
          card.dataset.kind = kind;
          card.classList.add('no-art');
          card.hidden = false;
          card.style.display = 'grid';
          document.querySelector('#context-clock').textContent = '11:04 am';
          document.querySelector('#context-weather').textContent = weatherText;
          document.querySelector('#context-title').textContent = 'Thanksgiving Day';
          document.querySelector('#context-subtitle').textContent = 'Monday, Oct 12';
          document.querySelector('#context-source').textContent = 'CALENDAR';
          document.body.classList.add('cast-display');
          const agenda = document.querySelector('#context-rows');
          const labels = ['Washers', 'New Moon', 'Thanksgiving Day', 'School pickup', 'Dentist appointment'];
          agenda.replaceChildren(...Array.from({length: rowCount}, (_, i) => {
            const item = document.createElement('span');
            item.textContent = labels[i] || `Event ${i + 1}`;
            return item;
          }));
          agenda.hidden = rowCount === 0;
          const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
          const clock = box('#context-clock');
          const parts = [box('#context-source'), box('.context-copy'), box('#context-rows'), box('#context-weather')];
          return {
            kind: card.dataset.kind,
            rowsHidden: agenda.hidden,
            clockSize: getComputedStyle(document.querySelector('#context-clock')).fontSize,
            agendaMaxHeight: getComputedStyle(agenda).maxHeight,
            agendaRowGap: getComputedStyle(agenda).rowGap,
            clockBox: clock,
            clockCenter: [clock.left + clock.width / 2, clock.top + clock.height / 2],
            weatherText: document.querySelector('#context-weather').textContent,
            weatherDisplay: getComputedStyle(document.querySelector('#context-weather')).display,
            weatherBox: box('#context-weather'),
            agendaBox: box('#context-rows'),
            chipBoxes: [...agenda.querySelectorAll('span')].map(chip => chip.getBoundingClientRect().toJSON()),
            cardBox: box('#context-card'),
            rowsHeight: box('#context-rows').height,
            copyBox: box('.context-copy'),
            overlaps: parts.some((a, i) => parts.slice(i + 1).some(b =>
              a.width > 0 && a.height > 0 && b.width > 0 && b.height > 0 &&
              a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top)),
          };
        }
        """,
        {"kind": kind, "rowCount": row_count, "weatherText": weather_text},
    )


def test_cast_calendar_centers_clock_and_fits_five_chips_above_it():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1024, 600), (1280, 800)):
            for kind in KINDS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.route("**/*", _route)
                result = _exercise(page, kind, 5)
                assert result["kind"] == kind
                assert result["rowsHidden"] is False
                assert float(result["clockSize"].replace("px", "")) >= 5.5 * 16
                assert result["agendaMaxHeight"] == f"{height * 0.36:g}px"
                assert result["agendaRowGap"] == f"{height * 0.007:g}px"
                assert len(result["chipBoxes"]) == 5
                assert all(chip["bottom"] <= result["clockBox"]["top"] for chip in result["chipBoxes"])
                assert result["copyBox"]["bottom"] <= result["clockBox"]["top"]
                assert abs(result["clockCenter"][0] - width / 2) < 1
                assert abs(result["clockCenter"][1] - height / 2) < 1
                assert result["clockBox"]["width"] > width * 0.25
                assert not result["overlaps"]
                page.close()
        browser.close()


def test_cast_single_calendar_event_and_ambient_agenda_center_clock_when_rows_are_empty():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for kind in KINDS:
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.route("**/*", _route)
            result = _exercise(page, kind, 0)
            assert result["rowsHidden"] is True
            assert result["rowsHeight"] == 0
            assert result["weatherText"] == ""
            assert result["weatherDisplay"] == "none"
            assert abs(result["clockCenter"][0] - 640) < 1
            assert abs(result["clockCenter"][1] - 400) < 1
            assert result["copyBox"]["bottom"] < result["clockBox"]["top"]
            assert result["clockBox"]["width"] > 1280 * 0.25
            assert not result["overlaps"]
            populated = _exercise(page, kind, 0, "17°C · Clear")
            assert populated["weatherText"] == "17°C · Clear"
            assert populated["weatherDisplay"] != "none"
            assert populated["weatherBox"]["top"] - populated["clockBox"]["bottom"] >= 1
            assert not populated["overlaps"]
            assert abs(populated["clockCenter"][0] - 640) < 1
            assert abs(populated["clockCenter"][1] - 400) < 1
            page.close()
        browser.close()
