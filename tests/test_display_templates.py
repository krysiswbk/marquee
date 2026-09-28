from pathlib import Path
import re
import unittest


DISPLAY = (Path(__file__).parents[1] / "output" / "index.html").read_text()


class DisplayTemplateTests(unittest.TestCase):
    def test_local_asset_cache_busters_match_release_version(self):
        version = (Path(__file__).parents[1] / "VERSION").read_text().strip()
        local_assets = re.findall(
            r'<(?:link rel="stylesheet" href|script src)="(/[^"?]+)(?:\?v=([^"&]+))?"',
            DISPLAY,
        )
        independently_versioned = {"/scene-themes.css": "2.9.7"}
        self.assertTrue(local_assets)
        for path, query_version in local_assets:
            with self.subTest(path=path):
                if path in independently_versioned:
                    self.assertEqual(query_version, independently_versioned[path])
                else:
                    self.assertEqual(query_version, version)

    def test_generic_context_collapses_when_artwork_is_missing(self):
        self.assertIn("context-card.no-art", DISPLAY)
        self.assertIn("contextCard.classList.toggle('no-art', !artVisible)", DISPLAY)
        self.assertIn("art.onerror = () =>", DISPLAY)

    def test_calendar_template_has_human_time_and_location_support(self):
        self.assertIn("function calendarRows(context)", DISPLAY)
        self.assertIn("context.allDay === true", DISPLAY)
        self.assertIn("context.location", DISPLAY)
        self.assertIn("minutes <= 24 * 60", DISPLAY)
        self.assertIn("context.type === 'calendar_event'", DISPLAY)

    def test_context_transition_uses_identity_and_cancels_stale_handoff(self):
        self.assertIn("MarqueeNowPlayingProgress.reconcile", DISPLAY)
        self.assertIn("if (transitionTimer) clearTimeout(transitionTimer)", DISPLAY)
        self.assertIn("prefers-reduced-motion: reduce", DISPLAY)

    def test_backend_enum_tokens_are_not_used_as_display_copy(self):
        self.assertIn("function friendlyEventState(context)", DISPLAY)
        self.assertIn("STARTING_SOON:'Starting soon'", DISPLAY)

    def test_home_surface_is_rich_on_kiosk_but_does_not_change_cast_clock(self):
        self.assertIn('id="idle-greeting"', DISPLAY)
        self.assertIn("context-demo=home", (Path(__file__).parents[1] / "cast" / "live-layout.html").read_text())
        self.assertIn("body.cast-display .idle-greeting", DISPLAY)
        self.assertIn("body.cast-display .idle-date", DISPLAY)

    def test_idle_body_state_cannot_hide_the_entire_document(self):
        self.assertNotIn("\n  .idle { display: none", DISPLAY)
        self.assertIn(".idle-screen { display: none", DISPLAY)
        self.assertIn("body.idle .idle-screen { display: flex; }", DISPLAY)
        self.assertIn("body.unavailable .idle-kicker", DISPLAY)
        self.assertIn("Media connection unavailable", DISPLAY)

    def test_live_visibility_cannot_hide_the_cast_clock(self):
        self.assertIn("CAST_DISPLAY || (LIVE_SURFACE", DISPLAY)
        self.assertIn("const homeVisible = block => CAST_DISPLAY ||", DISPLAY)

    def test_radar_preserves_timeline_and_swaps_frames_atomically(self):
        self.assertIn("object-fit: contain", DISPLAY)
        self.assertIn("function setRadarSource(source)", DISPLAY)
        self.assertIn("if (preload.decode) await preload.decode()", DISPLAY)
        self.assertIn("radar.dataset.source === wanted", DISPLAY)

    def test_radar_preserves_raw_colors_without_ambient_filtering(self):
        self.assertNotIn("--ambient-map-dim", DISPLAY)
        rule = DISPLAY.split(".weather-radar {", 1)[1].split("}", 1)[0]
        self.assertIn("filter: none", rule)
        self.assertIn("mix-blend-mode: normal", rule)

    def test_sports_controls_reference_real_elements(self):
        self.assertIn('id="sport-timebox"', DISPLAY)
        self.assertIn('id="sport-footer"', DISPLAY)

    def test_long_context_values_break_without_mutating_payload_text(self):
        for token in ("overflow-wrap:anywhere", "word-break:normal", "contextRows.dataset.summary"):
            self.assertIn(token, DISPLAY)
        self.assertIn("context.type === 'gaming' && rows.length > 1", DISPLAY)

    def test_fixed_stage_contracts_bound_intrinsic_rows_and_phone_gaming_queue(self):
        screens = (Path(__file__).parents[1] / "output" / "screens.css").read_text()
        for token in ("grid-template-rows:auto minmax(0,1fr) auto", "context-card[data-kind=gaming]",
                      "context-rows.phone-summary::after", "body .sport-footer{min-height:0"):
            self.assertIn(token, screens)

    def test_weather_condition_tokens_are_humanized_everywhere(self):
        self.assertIn("const readableCondition", DISPLAY)
        self.assertIn("partlycloudy:'Partly cloudy'", DISPLAY)
        self.assertNotIn("lastWx.condition || wxWord", DISPLAY)


class LiveLayoutAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (Path(__file__).parents[1] / "cast" / "live-layout.html").read_text()

    def test_controls_and_preview_have_accessible_names(self):
        self.assertIn('title="Interactive preview of the selected Live screen"', self.page)
        for field in ("sportsClockSize", "sportsArtworkSize", "sportsTextSize",
                      "sportsWeatherSize", "clockFormat"):
            self.assertIn(field, self.page)
        self.assertIn('label for="${id}"', self.page)
        self.assertIn('for="clockFormat"', self.page)
        self.assertIn('role="tablist"', self.page)
        self.assertIn('aria-pressed=', self.page)

    def test_dirty_save_discard_and_navigation_guard_are_visible(self):
        self.assertIn('id="discard"', self.page)
        self.assertIn("Unsaved changes", self.page)
        self.assertIn("beforeunload", self.page)
        self.assertIn("Draft discarded; current settings loaded.", self.page)
        self.assertIn('/control-shell.js', self.page)


class KioskInteractionAcceptanceTests(unittest.TestCase):
    def test_open_marquee_never_dismisses_or_hides_itself_on_interaction(self):
        self.assertNotIn("signalKioskActivity", DISPLAY)
        self.assertNotIn("kiosk-interacting", DISPLAY)
        self.assertNotIn("'/kiosk-activity'", DISPLAY)


class KioskFallbackContractTests(unittest.TestCase):
    def test_clock_fallback_is_driven_only_by_no_playing_payload(self):
        self.assertIn("if (!d.playing)", DISPLAY)
        self.assertIn("document.body.classList.add('idle')", DISPLAY)
        self.assertIn("document.body.classList.remove('idle')", DISPLAY)
        self.assertNotIn("fallback_every", DISPLAY)

    def test_context_identity_drives_clean_transition_between_plex_and_household(self):
        self.assertIn("MarqueeNowPlayingProgress.reconcile", DISPLAY)
        self.assertIn("if (key !== shownKey)", DISPLAY)
        self.assertIn("if (transitionTimer) clearTimeout(transitionTimer)", DISPLAY)


class FinalUiQaTests(unittest.TestCase):
    def test_canonical_fallback_select_gets_visible_label_association(self):
        page = (Path(__file__).parents[1] / "cast" / "settings-control.html").read_text()
        self.assertIn('label for="fallback-screen">Default view', page)
        self.assertIn('select id="fallback-screen" data-config-path="fallback.screen"', page)

    def test_screen_tester_selects_get_visible_label_associations(self):
        page = (Path(__file__).parents[1] / "cast" / "display-tests.html").read_text()
        for field in ("screen", "destination", "cast", "duration"):
            self.assertRegex(page, rf'<label>[^<]+<select id="{field}"')

    def test_attention_diagnostics_and_actions_have_stable_landmarks(self):
        page = (Path(__file__).parents[1] / "cast" / "attention-settings.html").read_text()
        for field in ("active-items", "display-decisions", "signals", "context",
                      "history", "save", "discard", "status"):
            self.assertIn(f'id="{field}"', page)

    def test_sports_demo_does_not_request_known_broken_headshot(self):
        self.assertNotIn("headshots/mma/players/full/2335750.png", DISPLAY)
        self.assertIn("data:image/svg+xml", DISPLAY)
