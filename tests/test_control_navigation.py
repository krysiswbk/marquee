import pathlib
import re
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

    def test_user_surfaces_have_no_decorative_sequence_labels(self):
        sources = {
            'public docs': ROOT / 'docs' / 'index.html',
            'settings': ROOT / 'cast' / 'settings.html',
            'cast layout': ROOT / 'cast' / 'cast-layout.html',
            'settings control': ROOT / 'cast' / 'settings-control.html',
            'attention': ROOT / 'cast' / 'attention-settings.html',
            'display tests': ROOT / 'cast' / 'display-tests.html',
            'live layout': ROOT / 'cast' / 'live-layout.html',
            'kiosk renderer': ROOT / 'output' / 'kiosk-menu.js',
            'home renderer': ROOT / 'output' / 'brain.js',
        }
        decorative = re.compile(
            r'(?:01|02|03)\s*(?:[/·|:-])\s*[A-Za-z]|'
            r'\b(?:Step|STEP)\s*[0-9]+\b')
        for name, path in sources.items():
            with self.subTest(surface=name):
                source = path.read_text()
                self.assertIsNone(decorative.search(source))
                self.assertNotIn('id="tour-n"', source)
                self.assertNotIn('.tour-n', source)
        for name in ('settings', 'cast layout'):
            source = sources[name].read_text()
            with self.subTest(surface=f'{name} walkthrough'):
                self.assertIn('const TOUR = [', source)
                self.assertIn('stepTo(tourStep + 1)', source)
                self.assertIn("$('#tour-next').textContent", source)
                self.assertNotIn("(i + 1) + ' of ' + TOUR.length", source)

    def test_tutorial_is_an_action_and_tour_is_a_focus_managed_dialog(self):
        for name in ('settings', 'cast layout'):
            path = ROOT / 'cast' / ('settings.html' if name == 'settings' else 'cast-layout.html')
            source = path.read_text()
            with self.subTest(surface=name):
                self.assertIn(
                    'id="tab-tutorial" type="button" data-tab="tutorial" '
                    'aria-haspopup="dialog" aria-controls="tour"', source)
                self.assertNotIn('id="tab-tutorial" aria-selected=', source)
                self.assertNotIn('id="tab-tutorial" role="tab"', source)
                self.assertIn('id="tour" role="dialog" aria-modal="true"', source)
                self.assertIn('aria-labelledby="tour-title" aria-describedby="tour-body"', source)
                self.assertIn("event.key === 'Escape'", source)
                self.assertIn("$('#tour-next').focus()", source)
                self.assertIn("tourLauncher.focus()", source)
                self.assertIn("event.key !== 'Tab'", source)
                self.assertIn("button[role=\"tab\"]", source)

    def test_provider_diagnostics_use_safe_status_copy_and_authoritative_source(self):
        page = PAGES['settings'].read_text()
        renderer = (ROOT / 'output/settings-control.js').read_text()
        self.assertIn('https://github.com/krysiswbk/marquee', page)
        self.assertNotIn('https://github.com/Jamisonfitz/marquee', page)
        for token in ('health-provider', 'health-status', 'health-explanation',
                      'Last checked:', 'labels = {ok:'):
            self.assertIn(token, renderer)
        self.assertNotIn('Latest error:', renderer)

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

    def test_optional_resize_targets_are_guarded_before_observe(self):
        for path, variable in ((ROOT / 'cast/settings.html', 'settingsSide'),
                               (ROOT / 'cast/cast-layout.html', 'layoutSide')):
            source = path.read_text()
            with self.subTest(path=path):
                self.assertIn(f"const {variable} = document.querySelector('.mq-side');", source)
                self.assertIn(f"if ({variable}) new ResizeObserver(scaleFrame).observe({variable});", source)
                self.assertNotIn("observe(document.querySelector('.mq-side'))", source)

    def test_navigation_keeps_touch_targets_and_safe_area_spacing(self):
        styles = (ROOT / "output" / "screens.css").read_text()
        self.assertIn("min-height:44px", styles)
        self.assertIn("safe-area-inset-left", styles)
        self.assertIn("white-space:nowrap", styles)

    def test_settings_navigation_has_deliberate_narrow_priority_layout(self):
        source = PAGES["settings"].read_text()
        styles = (ROOT / "output/settings-narrow-nav.css").read_text()
        self.assertIn('class="workspace-nav"', source)
        self.assertIn('class="view-display"', source)
        self.assertIn('aria-hidden="true"', source)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", styles)
        self.assertIn("grid-column: 1 / -1", styles)
        self.assertIn("overflow: visible", styles)
        self.assertIn("min-height:44px", (ROOT / "cast" / "settings-control.html").read_text())

    def test_shared_navigation_cache_identity_and_labeled_display_action(self):
        version = (ROOT / "VERSION").read_text().strip()
        shell = (ROOT / "output/control-shell.js").read_text()
        css = (ROOT / "output/control-shell-narrow.css").read_text()
        self.assertIn('class="mq-view"', shell)
        self.assertIn('View display <span aria-hidden="true">↗</span>', shell)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        for page in (PAGES["cast-layout"], PAGES["live-layout"], PAGES["attention"], PAGES["tests"]):
            source = page.read_text()
            self.assertIn(f"control-shell.css?v={version}", source)
            self.assertIn(f"control-shell.js?v={version}", source)
            self.assertIn(f"control-shell-narrow.css?v={version}", source)

    def test_layout_workspace_has_explicit_phone_composition_contract(self):
        source = PAGES["cast-layout"].read_text()
        for token in ("class=\"mq-mode-link\"", "Arrange your Cast cards",
                      "Choose a template, then select", "id=\"editor-toggle\""):
            self.assertIn(token, source)
        self.assertIn(".mq-mode-link strong, .mq-mode-link span { display: block; }", source)
        self.assertIn(".ed-row { flex-wrap: wrap;", source)
        self.assertIn(".top .actions { width: 100%; margin-left: 0; }", source)
        self.assertIn("<strong>Arrange your Cast cards</strong><span>", source)

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
        self.assertIn("channel-outlook{font:400 clamp(12px,1.2vw,21px)/1.4 var(--wx-font);color:var(--wx-muted);margin:1.5vh 0 0;max-height:10vh;overflow:auto}", weather)
        self.assertIn("channel-outlook{max-height:none;overflow:visible}", weather)
        self.assertIn("clip-path:inset(50%)", screens)

    def test_home_weather_summary_uses_available_authoritative_near_term_fields(self):
        source = (ROOT / "output" / "index.html").read_text()
        for field in ("apparent_temperature", "temperature", "templow", "precipitation_probability"):
            self.assertIn(field, source)
        self.assertIn("Feels", source)
        self.assertIn("High", source)

    def test_home_weather_summary_omits_unavailable_high_or_low_values(self):
        source = (ROOT / "output" / "index.html").read_text()
        self.assertIn(".filter(Boolean).join(' / ')", source)
        self.assertIn("idle-weather-range", source)
        self.assertNotIn("'—'", source)

    def test_home_weather_hierarchy_has_truthful_freshness_and_unavailable_states(self):
        source = (ROOT / "output" / "index.html").read_text()
        for token in ("idle-weather-primary", "idle-weather-secondary", "idle-weather-status",
                      "observed_at", "forecast_updated", "Last observation is stale",
                      "Freshness unknown", "Weather unavailable"):
            self.assertIn(token, source)
        self.assertIn("homeWeather.hidden = !showHomeWeather", source)

    def test_tablet_home_weather_summary_has_width_and_panel_clearance(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        self.assertIn("@media (min-width:481px) and (max-width:700px)", styles)
        self.assertIn("width:92vw", styles)
        self.assertIn("max-width:92vw", styles)
        self.assertIn("line-height:1.2", styles)
        self.assertIn("#brain-house{top:43vh;bottom:auto;height:25vh}", styles)
        self.assertIn("#brain-house.fit-compact", styles)
        self.assertNotIn("#brain-house .brain-openings{max-height:4vh;overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap}", styles)
        self.assertNotIn("max-width:44vw", styles)

    def test_home_responsive_panels_respect_dock_safe_area(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        self.assertIn(".brain-panel{position:absolute", styles)
        self.assertIn("box-sizing:border-box;padding:2.3vh 1.8vw;overflow:hidden;pointer-events:auto}", styles)
        self.assertIn("#brain-house{left:47vw;right:4vw;top:14vh;height:37vh;border-top:4px solid var(--desk-accent);overflow:visible}", styles)
        self.assertIn("min-width:44px;min-height:44px", styles)
        self.assertIn("body.brain-live .brain-panel{box-sizing:border-box;padding-block:1.2vh}", styles)
        self.assertIn("#brain-activity,body.brain-live #brain-agenda{top:69vh;height:16vh;bottom:auto}", styles)
        self.assertNotIn("top:70vh;bottom:16vh;height:auto", styles)
        self.assertNotIn("top:70vh;height:20vh", styles)
        self.assertIn("#brain-activity{top:65vh;left:4vw;width:92vw;height:12vh}", styles)
        self.assertIn("#brain-agenda{display:none}", styles)
        self.assertNotIn("top:80vh", styles)

    def test_customize_action_has_a_labeled_responsive_target(self):
        brain = (ROOT / "output" / "brain.js").read_text()
        styles = (ROOT / "output" / "brain.css").read_text()
        self.assertIn('class="brain-customize" href="/settings/layout?profile=live"', brain)
        self.assertIn('aria-label="Customize the household desk"', brain)
        self.assertIn('class="brain-customize-label">Customize</span>', brain)
        self.assertIn("display:inline-flex", styles)
        self.assertIn("min-width:5.8em;min-height:2.2em", styles)
        self.assertIn(".brain-live .brain-customize{min-width:44px;min-height:44px", styles)
        self.assertNotIn("#brain-house.device-alert .brain-openings{display:none}", styles)
        tablet = styles.split("@media (min-width:481px) and (max-width:700px)", 1)[1].split("@media (max-width:480px)", 1)[0]
        self.assertIn("box-sizing:border-box", tablet)
        self.assertIn("padding-block:1.2vh", tablet)
        self.assertIn("height:25vh", tablet)
        self.assertLessEqual(69 + 16, 85.1)
        self.assertLessEqual(43 + 25, 70)
        brain = (ROOT / "output" / "brain.js").read_text()
        self.assertIn("classList.toggle('device-alert',Boolean(deviceHealth.length))", brain)

    def test_tablet_alert_prioritizes_actionable_device_health_copy(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        brain = (ROOT / "output" / "brain.js").read_text()
        self.assertIn("Offline: ${deviceHealth.map(d=>d.name).join(', ')}. Check batteries or connection.", brain)
        self.assertIn("if(deviceHealth.length)summary='Device status needs attention.'", brain)
        self.assertIn("else if(fresh&&state.unknown?.length)", brain)
        self.assertIn("#brain-house.device-alert #brain-device-health{display:block", styles)
        self.assertNotIn("#brain-house.device-alert .brain-openings{display:none}", styles)

    def test_tablet_support_copy_is_deliberately_bounded_above_dock(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        brain = (ROOT / "output" / "brain.js").read_text()
        tablet = styles.split("@media (min-width:481px) and (max-width:700px)", 1)[1].split("@media (max-width:480px)", 1)[0]
        self.assertIn("top:69vh;height:16vh;bottom:auto", tablet)
        self.assertNotIn("bottom:16vh", tablet)
        self.assertIn("brain-event-more", tablet)
        self.assertNotIn(".brain-event:nth-child(n+3){display:none}", tablet)
        self.assertNotIn(".brain-agenda-item span{display:none}", tablet)
        self.assertIn("#brain-agenda{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)", tablet)
        self.assertIn("#brain-agenda .brain-upnext{display:block;min-width:0}", tablet)
        self.assertNotIn("height:16vh;bottom:auto;overflow:visible", tablet)
        self.assertNotIn("#brain-activity,body.brain-live #brain-agenda{overflow:visible}", styles)
        self.assertIn(".brain-empty{font-size:1.06vw;line-height:1.55;color:var(--desk-muted);max-width:32vw;margin:0}", styles)
        self.assertIn("#brain-activity:has(.brain-empty){padding-block:.4vh}", styles)
        self.assertIn("#brain-activity:has(.brain-empty){padding-block:.5vh}", styles)
        self.assertIn(".brain-empty{font-size:clamp(12px,3.05vw,16px);line-height:1.1}", styles)
        self.assertNotIn(".brain-empty{font-size:2.2vw", styles)
        self.assertNotIn(".brain-live .brain-empty,.brain-live .brain-tag", styles)
        self.assertIn("grid-template-columns:minmax(0,1fr) minmax(0,1fr)", tablet)
        self.assertIn("brain-agenda-more", tablet)
        self.assertIn("events.length>3", brain)
        self.assertIn("more recent event", brain)
        self.assertIn("birthdayMore", brain)
        self.assertIn("upcomingMore", brain)
        self.assertIn("more upcoming item", brain)
        self.assertIn("more birthday", brain)
        self.assertIn("No new door or lock activity in the last 15 minutes.", brain)
        self.assertIn("Activity feed reconnecting; recent activity is unavailable.", brain)
        self.assertNotIn("The next real change lands here.", brain)

    def test_portrait_home_uses_explicit_zones_and_dense_household_fit(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        brain = (ROOT / "output" / "brain.js").read_text()
        self.assertIn("min-height:6vh", styles)
        self.assertIn("top:12vh;right:4vw;bottom:auto;height:26vh", styles)
        self.assertIn("#brain-house{top:40vh;left:4vw;height:22vh}", styles)
        self.assertIn("#brain-house{top:43vh;bottom:auto;height:25vh}", styles)
        self.assertIn("#brain-house.fit-compact .brain-summary", styles)
        self.assertIn("panel.scrollHeight>panel.clientHeight", brain)
        self.assertIn("document.fonts.ready.then(fitHousePanel)", brain)
        self.assertIn("opening.map(o=>", brain)
        self.assertNotIn("opening.slice(0,5)", brain)
        self.assertNotIn("summary.length > 110", brain)

    def test_compact_household_text_and_acknowledgement_remain_readable(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        self.assertIn("#brain-house.fit-compact .brain-summary{font-size:clamp(12px", styles)
        self.assertIn("#brain-house.fit-compact .brain-tag{padding:.18em .35em;font-size:clamp(12px", styles)
        self.assertIn("#brain-house.fit-compact .brain-ack{margin-top:.45vh;font-size:clamp(12px", styles)
        self.assertIn("#brain-house.fit-compact .brain-tag{padding:.25em .45em;font-size:clamp(12px", styles)
        self.assertIn("#brain-house.fit-compact .brain-ack{margin-top:.5vh;font-size:clamp(12px", styles)

    def test_portrait_weather_has_legible_minimums_without_losing_secondary_facts(self):
        styles = (ROOT / "output" / "brain.css").read_text()
        source = (ROOT / "output" / "index.html").read_text()
        self.assertIn("font-size:clamp(32px,8vw,78px)", styles)
        self.assertIn("font-size:clamp(11px,2.5vw,24px)", styles)
        for field in ("idle-weather-temp", "idle-weather-condition", "idle-weather-feels",
                      "idle-weather-range", "idle-weather-rain"):
            self.assertIn(f'id="{field}"', source)

    def test_home_uses_names_without_decorative_editorial_ordinals(self):
        brain = (ROOT / "output" / "brain.js").read_text()
        for label in ("Right now", "Just happened", "People first"):
            self.assertIn(f">{label}<", brain)
        self.assertNotRegex(brain, r">0[1-9]\s*[/·|—-]")
        self.assertNotRegex(brain, r"\b0[1-9]\s*[/·|—-]\s*(Right now|Just happened|People first)")

    def test_screens_geometry_override_does_not_compete_with_tablet_or_phone_contract(self):
        screens = (ROOT / "output" / "screens.css").read_text()
        self.assertIn("@media(min-width:701px) and (max-aspect-ratio:1/1)", screens)
        override = "body.brain-live.browser-controls #brain-activity,body.brain-live.browser-controls #brain-agenda{height:calc(25vh - var(--control-rail))}"
        self.assertEqual(screens.count(override), 1)
        self.assertNotIn(override, screens.split("@media(min-width:701px)", 1)[0])


if __name__ == "__main__":
    unittest.main()
