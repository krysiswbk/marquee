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
        self.assertIn("const state = String(nowPlaying?.state || '').toLowerCase()", MENU)
        self.assertIn("const availability = String(nowPlaying?.availability || '').toLowerCase()", MENU)
        self.assertIn("state === 'stale'", MENU)
        self.assertIn("state === 'stopped'", MENU)
        self.assertIn("Nothing is playing", MENU)
        self.assertIn("Media service unavailable", MENU)
        self.assertIn("state:'idle'", MENU)
        # No selected browse item may replace an authoritative Plex response.
        self.assertIn("if (interrupted || !view || view === 'plex') return payload", MENU)

    def test_explicit_plex_destination_renders_identity_and_progress_from_payload(self):
        self.assertIn("const plexActive = view === 'plex' && nowPlaying?.playing === true", MENU)
        self.assertIn("if (interrupted || !view || view === 'plex') return payload", MENU)
        self.assertIn("progressState = window.MarqueeNowPlayingProgress.reconcile(d, progressState", INDEX)
        self.assertIn("render(d);", INDEX)
        self.assertIn("const kioskPlaybackActive = LIVE_SURFACE && ATTENTION_DISPLAY === 'kiosk'", MENU)
        self.assertIn("document.body.classList.toggle('kiosk-playback-active', kioskPlaybackActive)", MENU)

    def test_idle_unavailable_surface_does_not_reuse_media_identity(self):
        self.assertIn("No previous title or artwork is retained here", MENU)
        self.assertNotIn("nowPlaying.title", MENU)
        self.assertNotIn("nowPlaying.key", MENU)
        self.assertIn("data-kiosk-retry", MENU)

    def test_idle_composition_is_concise_and_weather_is_grouped(self):
        self.assertIn("const unavailableMark = unavailable || stale ?", MENU)
        self.assertIn("const weatherLabels = ['Temperature', 'Conditions', 'Feels like', 'High and low']", MENU)
        self.assertIn('class="kiosk-weather-separator" aria-hidden="true"', MENU)
        self.assertIn('class="kiosk-weather-fact" aria-label=', MENU)
        self.assertNotIn("Nothing needs your attention right now", MENU)
        self.assertNotIn("The room is quiet. Choose Home", MENU)
        self.assertIn("display:inline-block;width:fit-content;max-width:100%", SCREENS)
        self.assertIn(".now-playing-surface .kiosk-now-playing-head h1:focus-visible", SCREENS)
        self.assertIn("outline-offset:7px", SCREENS)
        self.assertIn("idle-weather-feels", MENU)
        self.assertIn("Feels like", MENU)

    def test_kiosk_playback_removes_technical_primary_metadata_and_bounds_art(self):
        self.assertIn("const kioskPlayback = LIVE_SURFACE && ATTENTION_DISPLAY === 'kiosk';", INDEX)
        self.assertIn("!kioskPlayback && c.showMediaInfo !== false", INDEX)
        self.assertIn("!kioskPlayback && shown.has('ratings')", INDEX)
        self.assertIn("!kioskPlayback && shown.has('stream')", INDEX)
        self.assertIn("body.kiosk-now-playing .stage", SCREENS)
        self.assertIn("body.kiosk-now-playing .stage,body.kiosk-playback-active .stage", SCREENS)
        self.assertIn("grid-template-areas:\"category poster\"", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-poster", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-streetframe,body.kiosk-now-playing .b-nowplaying,body.kiosk-playback-active .b-streetframe,body.kiosk-playback-active .b-nowplaying{display:none!important;}", SCREENS)
        self.assertIn("width:min(18vw,260px);height:auto;max-height:min(44vh,390px);aspect-ratio:2/3", SCREENS)
        self.assertIn("body.kiosk-playback-active .b-streetframe,body.kiosk-playback-active .b-nowplaying", SCREENS)
        self.assertIn("body.kiosk-playback-active .stage > .b-identity", SCREENS)
        self.assertIn("body.kiosk-playback-active .b-progress", SCREENS)
        self.assertIn("body.kiosk-now-playing .stage > .b-identity", SCREENS)
        self.assertIn("position:static!important;inset:auto!important;grid-area:auto!important", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-poster,", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-progress,", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-device,", SCREENS)
        self.assertIn("body.kiosk-playback-active .stage > .b-identity", SCREENS)
        self.assertIn("body.kiosk-playback-active .b-poster", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-poster,body.kiosk-playback-active .b-poster", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-progress,body.kiosk-playback-active .b-progress", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-device,body.kiosk-now-playing .b-viewer", SCREENS)
        self.assertIn("body.kiosk-now-playing .b-device *,body.kiosk-playback-active .b-device *", SCREENS)

    def test_street_now_playing_restores_the_established_screening_composition(self):
        self.assertIn("body.kiosk-now-playing[data-template=street] .stage{display:block;padding:0;}", SCREENS)
        self.assertIn("body.kiosk-now-playing[data-template=street] .b-streetframe{display:block!important", SCREENS)
        self.assertIn("body.kiosk-now-playing[data-template=street] .b-nowplaying{display:block!important", SCREENS)
        self.assertIn("left:var(--street-frame-left,63.59375vw)", SCREENS)
        self.assertIn("left:var(--street-sign-left,62.2vw)", SCREENS)
        self.assertIn("body.kiosk-now-playing[data-template=street] .b-poster{left:66.4vw;top:18.75vh;width:25vw;height:60vh", SCREENS)
        self.assertIn("body.kiosk-now-playing[data-template=street] .b-progress{left:5.5vw;top:86vh", SCREENS)

    def test_authoritative_apparent_temperature_accepts_numeric_strings_only(self):
        self.assertIn("lastWx?.apparent_temperature == null || lastWx.apparent_temperature === ''", INDEX)
        self.assertIn("? null : Number(lastWx.apparent_temperature)", INDEX)
        self.assertIn("Number.isFinite(apparentTemperature)", INDEX)
        weather_channel = (ROOT / "output/weather-channel.js").read_text()
        self.assertIn("Number(model.apparent_temperature)", weather_channel)
        self.assertIn("Number.isFinite(apparentTemperature)", weather_channel)

    def test_compact_sports_and_context_weather_include_authoritative_feels_like(self):
        self.assertIn("const compactWeatherLine = weather =>", INDEX)
        self.assertIn("Number.isFinite(apparent) ? ` · Feels ${Math.round(apparent)}°` : ''", INDEX)
        self.assertIn("sportsWeather.textContent = compactWeatherLine(lastWx)", INDEX)
        self.assertIn("$('context-weather').textContent = compactWeatherLine(lastWx)", INDEX)
        self.assertIn("white-space:normal;overflow-wrap:anywhere", SCREENS)

    def test_phone_dock_truncates_long_household_copy(self):
        brain = (ROOT / "output/brain.css").read_text()
        self.assertIn(".brain-dock-copy{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}", brain)
        self.assertIn(".brain-dock-people{display:none!important}", brain)

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

    def test_non_phone_progress_is_directly_anchored_above_the_kiosk_dock(self):
        self.assertIn(
            "body.kiosk-now-playing .b-progress,body.kiosk-playback-active .b-progress{position:fixed!important",
            SCREENS,
        )
        self.assertIn(
            "inset:auto auto calc(var(--kiosk-lower-safe-area) + 8px) 6vw!important",
            SCREENS,
        )
        self.assertIn("z-index:9001", SCREENS)
        self.assertNotIn("body.kiosk-now-playing .stage,body.kiosk-playback-active .stage{bottom:", SCREENS)

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

    def test_phone_playback_attaches_bounded_art_to_editorial_content(self):
        self.assertIn('grid-template-areas:"category poster" "identity poster" "meta poster" "progress poster" "device device"', SCREENS)
        self.assertIn("justify-self:end", SCREENS)
        self.assertIn("max-height:198px", SCREENS)
        self.assertIn("Check back when the next event is published.", MENU)
        self.assertNotIn("item.score", (ROOT / "output/attention-settings.js").read_text())

    def test_narrow_orbit_cannot_create_a_horizontal_scroller(self):
        self.assertIn("body.browser-controls{overflow-x:hidden}", SCREENS)
        self.assertIn("overflow-x:hidden;overflow-y:auto", SCREENS)
        self.assertIn("padding:clamp(88px,12vh,108px) 20px 88px", SCREENS)
        self.assertIn("body.kiosk-playback-active .stage{display:grid!important", SCREENS)
        # The responsive orbit is a background layer, so it remains ambient
        # without becoming scrollable content at any narrow width.
        self.assertIn("background-size:72vw 72vw,auto,auto,auto", SCREENS)
        self.assertIn("background-position:right -18% top 13%", SCREENS)
        self.assertIn("background-size:92vw 92vw,auto,auto,auto", SCREENS)
        self.assertIn("background-position:right -31% top 9%", SCREENS)


if __name__ == "__main__":
    unittest.main()
