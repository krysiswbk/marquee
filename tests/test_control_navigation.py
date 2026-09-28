import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
PAGES = {
    "settings": ROOT / "cast" / "settings-control.html",
    "cast-layout": ROOT / "cast" / "cast-layout.html",
    "live-layout": ROOT / "cast" / "live-layout.html",
    "attention": ROOT / "cast" / "attention-settings.html",
    "tests": ROOT / "cast" / "display-tests.html",
    "live": ROOT / "output" / "kiosk-menu.js",
}
CANONICAL_ROUTES = ('/settings', '/settings/layout?profile=cast',
                    '/settings/attention', '/settings/tests')


class ControlNavigationTests(unittest.TestCase):
    def test_every_control_surface_uses_shared_navigation(self):
        for name, path in PAGES.items():
            if name in ("live", "settings"):
                continue
            with self.subTest(page=name):
                self.assertIn('/control-shell.js', path.read_text())
        shared = (ROOT / 'output/control-shell.js').read_text()
        for route in CANONICAL_ROUTES:
            self.assertIn(route, shared)
        self.assertIn('aria-current="page"', shared)
        settings = PAGES['settings'].read_text()
        self.assertIn('aria-label="Settings workspaces"', settings)
        for route in CANONICAL_ROUTES:
            self.assertIn(f'href="{route}"', settings)

    def test_layout_help_product_info_and_display_remain_accessible(self):
        settings = PAGES['settings'].read_text()
        cast = PAGES['cast-layout'].read_text()
        self.assertIn('id="running-version"', settings)
        self.assertIn('id="release-notes"', settings)
        self.assertIn('/settings/layout?profile=cast', settings)
        for capability in ('id="share-look"', 'id="import-look"', 'id="export"',
                           'id="import"', 'id="sessions-btn"', 'id="scan"'):
            self.assertIn(capability, cast)
        self.assertIn('href="/live"', (ROOT / 'output/control-shell.js').read_text())

    def test_editors_warn_before_abandoning_unsaved_drafts(self):
        sources = {
            'settings': PAGES['settings'].read_text() + (ROOT / 'output/settings-control.js').read_text(),
            'cast-layout': PAGES['cast-layout'].read_text(),
            'live-layout': PAGES['live-layout'].read_text(),
            'attention': PAGES['attention'].read_text() + (ROOT / 'output/attention-settings.js').read_text(),
        }
        for name, source in sources.items():
            with self.subTest(page=name):
                self.assertIn('beforeunload', source)

    def test_canonical_pages_do_not_link_to_retired_routes(self):
        retired = ('href="/admin', 'href="/live-settings"',
                   'href="/settings-preview"', 'href="/?tab=')
        for name, path in PAGES.items():
            if name == 'live':
                continue
            source = path.read_text()
            with self.subTest(page=name):
                for link in retired:
                    self.assertNotIn(link, source)

    def test_display_navigation_excludes_cast_and_editor(self):
        source = PAGES["live"].read_text()
        self.assertIn("params.has('demo') || params.has('edit')", source)
        self.assertIn("['/live', '/kiosk'].includes(location.pathname)", source)

    def test_display_navigation_exposes_direct_destinations_with_explicit_overflow(self):
        source = PAGES["live"].read_text()
        self.assertIn('class="kiosk-primary"', source)
        self.assertIn('class="kiosk-more"', source)
        self.assertIn('aria-label="Marquee destinations"', source)
        self.assertIn('allDestinations()', source)
        self.assertIn('ResizeObserver', source)
        self.assertIn('Connection unavailable', source)

    def test_navigation_keeps_touch_targets_and_safe_area_spacing(self):
        styles = (ROOT / "output" / "screens.css").read_text()
        self.assertIn("min-height:44px", styles)
        self.assertIn("safe-area-inset-left", styles)
        self.assertIn("white-space:nowrap", styles)

    def test_weather_is_priority_destination_and_dialog_close_is_synchronized(self):
        source = PAGES["live"].read_text()
        self.assertIn("destinationPriority", source)
        self.assertIn("weather:95", source)
        self.assertIn("menu.addEventListener('close'", source)
        self.assertIn("menu.addEventListener('cancel'", source)
        self.assertIn("more.setAttribute('aria-expanded', 'false')", source)

    def test_narrow_weather_controls_flow_without_small_touch_targets(self):
        weather = (ROOT / "output" / "weather-channel.css").read_text()
        screens = (ROOT / "output" / "screens.css").read_text()
        self.assertIn("min-height:44px", weather)
        self.assertIn("channel-outlook{max-height:none;overflow:visible}", weather)
        self.assertIn("clip-path:inset(50%)", screens)

    def test_home_weather_summary_uses_available_authoritative_near_term_fields(self):
        source = (ROOT / "output" / "index.html").read_text()
        for field in ("apparent_temperature", "temperature", "templow", "precipitation_probability"):
            self.assertIn(field, source)
        self.assertIn("Feels", source)
        self.assertIn("High", source)


if __name__ == "__main__":
    unittest.main()
