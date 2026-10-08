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
          document.querySelector('#context-art').hidden = true;
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
            if (kind === 'ambient_agenda') {
              const when = document.createElement('time');
              when.textContent = `Tomorrow · ${6 + i}:00 PM`;
              const title = document.createElement('strong');
              title.textContent = labels[i] || `Event ${i + 1}`;
              item.className = 'context-agenda-row';
              item.append(when, title);
            } else item.textContent = labels[i] || `Event ${i + 1}`;
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
            clockDisplay: getComputedStyle(document.querySelector('.context-time')).display,
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


def test_cast_calendar_matches_kiosk_agenda_and_fits_five_events():
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
                assert result["clockDisplay"] == "none"
                assert float(result["clockSize"].replace("px", "")) >= 16
                assert result["agendaMaxHeight"] == f"{height * 0.72:g}px"
                assert result["agendaRowGap"] == "0px"
                assert len(result["chipBoxes"]) == 5
                assert all(chip["left"] >= result["copyBox"]["right"] for chip in result["chipBoxes"])
                assert all(chip["width"] > width * 0.3 for chip in result["chipBoxes"])
                assert result["copyBox"]["width"] > width * 0.35
                assert not result["overlaps"]
                page.close()
        browser.close()


def test_cast_calendar_hides_empty_rows_and_clock_without_clipping_the_event():
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
            assert result["clockDisplay"] == "none"
            assert result["copyBox"]["width"] > 1280 * 0.35
            assert not result["overlaps"]
            populated = _exercise(page, kind, 0, "17°C · Clear")
            assert populated["weatherText"] == "17°C · Clear"
            assert populated["weatherDisplay"] == "none"
            assert not populated["overlaps"]
            page.close()
        browser.close()
