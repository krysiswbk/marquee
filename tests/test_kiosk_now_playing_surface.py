import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MENU = (ROOT / "output/kiosk-menu.js").read_text()
SCREENS = (ROOT / "output/screens.css").read_text()
INDEX = (ROOT / "output/index.html").read_text()


class KioskNowPlayingSurfaceContractTests(unittest.TestCase):
    def test_plex_uses_the_authoritative_payload_for_every_lifecycle_state(self):
        self.assertIn("nowPlaying = payload", MENU)
        self.assertIn("view === 'plex'", MENU)
        self.assertIn("nowPlaying?.playing === true", MENU)
        self.assertIn("nowPlaying?.state === 'unavailable'", MENU)
        self.assertIn("Nothing is playing", MENU)
        self.assertIn("Media service unavailable", MENU)
        self.assertIn("state:'idle'", MENU)
        # No selected browse item may replace an authoritative Plex response.
        self.assertIn("if (interrupted || !view || view === 'plex') return payload", MENU)

    def test_idle_unavailable_surface_does_not_reuse_media_identity(self):
        self.assertIn("No previous title or artwork is retained here", MENU)
        self.assertNotIn("nowPlaying.title", MENU)
        self.assertNotIn("nowPlaying.key", MENU)
        self.assertIn("data-kiosk-retry", MENU)

    def test_idle_composition_is_concise_and_weather_is_grouped(self):
        self.assertIn("const unavailableMark = unavailable ?", MENU)
        self.assertIn("const weatherLabels = ['Temperature', 'Conditions', 'High and low']", MENU)
        self.assertIn('class="kiosk-weather-separator" aria-hidden="true"', MENU)
        self.assertIn('class="kiosk-weather-fact" aria-label=', MENU)
        self.assertNotIn("Nothing needs your attention right now", MENU)
        self.assertNotIn("The room is quiet. Choose Home", MENU)
        self.assertIn("display:inline-block;width:fit-content;max-width:100%", SCREENS)
        self.assertIn(".now-playing-surface .kiosk-now-playing-head h1:focus-visible", SCREENS)
        self.assertIn("outline-offset:7px", SCREENS)

    def test_navigation_and_touch_contract(self):
        self.assertIn('class="kiosk-home-action"', MENU)
        self.assertIn("e.key === 'Escape'", MENU)
        self.assertIn("change('')", MENU)
        self.assertIn("min-height:48px", SCREENS)
        self.assertIn("Return to Home", MENU)

    def test_responsive_surface_and_cache_identity(self):
        self.assertIn(".kiosk-section.now-playing-surface", SCREENS)
        self.assertIn("@media(max-width:700px)", SCREENS)
        self.assertIn("@media(max-width:480px)", SCREENS)
        version = (ROOT / "VERSION").read_text().strip()
        self.assertIn(f"kiosk-menu.js?v={version}", INDEX)

    def test_progress_uses_reconciled_display_state_and_resets_outside_playback(self):
        source = (ROOT / "output/index.html").read_text()
        helper = (ROOT / "output/now-playing-progress.js").read_text()
        self.assertIn("MarqueeNowPlayingProgress.reconcile", source)
        self.assertIn("prior displayed/estimated offset", helper)
        self.assertIn("SOURCE_JITTER_TOLERANCE_MS = 2000", helper)
        self.assertIn("progressState = window.MarqueeNowPlayingProgress.reconcile(d, progressState", source)

    def test_compact_weather_facts_have_nonempty_fact_separators(self):
        self.assertIn("weather-fact-separator", SCREENS)
        self.assertIn("border-inline-start", SCREENS)
        self.assertIn("padding-inline-start", SCREENS)
        self.assertIn(".idle-weather-primary", SCREENS)
        self.assertIn(".idle-weather-secondary", SCREENS)
        self.assertIn("markWeatherFactSeparators", INDEX)

    def test_weather_fact_marking_skips_empty_facts_without_double_boundaries(self):
        self.assertIn("const present = Boolean(fact.textContent.trim())", INDEX)
        self.assertIn("present && seen", INDEX)
        self.assertIn("if (present) seen = true", INDEX)

    def test_narrow_orbit_cannot_create_a_horizontal_scroller(self):
        self.assertIn("body.browser-controls{overflow-x:hidden}", SCREENS)
        self.assertIn("overflow-x:hidden;overflow-y:auto", SCREENS)
        # The responsive orbit is a background layer, so it remains ambient
        # without becoming scrollable content at any narrow width.
        self.assertIn("background-size:72vw 72vw,auto,auto,auto", SCREENS)
        self.assertIn("background-position:right -18% top 13%", SCREENS)
        self.assertIn("background-size:92vw 92vw,auto,auto,auto", SCREENS)
        self.assertIn("background-position:right -31% top 9%", SCREENS)


if __name__ == "__main__":
    unittest.main()
