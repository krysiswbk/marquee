from pathlib import Path


ROOT = Path(__file__).parents[1]
MENU = (ROOT / "output/kiosk-menu.js").read_text()
SCREENS = (ROOT / "output/screens.css").read_text()
INDEX = (ROOT / "output/index.html").read_text()


def test_forced_destinations_have_purposeful_category_renderers():
    for name in ("categoryFor", "renderSports", "renderAgenda", "renderMedia", "renderAmbient"):
        assert name in MENU
    assert "sportViews" in MENU and "mediaViews" in MENU
    assert "renderDestination(view, list)" in MENU


def test_rail_uses_unique_product_owned_current_color_marks():
    for token in ("const homeIcon = '<svg", "const moreIcon = '<svg", "currentColor",
                  "aria-hidden=\"true\"", "plex: ['Now playing'", "nhl: ['NHL'",
                  "ufc: ['UFC'", "pfl: ['PFL'", "weather: ['Weather'", "calendar: ['Calendar'"):
        assert token in MENU or token in SCREENS
    assert "🏒" not in MENU and "🥊" not in MENU and "🥋" not in MENU
    assert "📺" not in MENU and "📅" not in MENU
    assert ".kiosk-icon svg{display:block" in SCREENS
    assert "fill:none;stroke:currentColor" in SCREENS
    assert "${esc(glyph)}" not in MENU


def test_large_display_rail_has_explicit_scale_and_balanced_distribution_tiers():
    for token in (
        "@media(min-width:701px)",
        "@media(min-width:1200px)",
        ".kiosk-primary{flex:1 1 auto;justify-content:center;gap:6px}",
        ".kiosk-icon{width:18px;height:18px}",
        ".kiosk-icon{width:22px;height:22px}",
        ".kiosk-brand{min-width:88px}",
        ".kiosk-brand{min-width:112px;font-size:17px}",
    ):
        assert token in SCREENS
    assert "font-size:16px" in SCREENS and "font-size:17px;padding-inline:12px" in SCREENS
    assert "min-height:44px" in SCREENS


def test_sports_contract_keeps_matchup_status_and_next_event_hierarchy():
    for token in ("kiosk-sport-feature", "kiosk-matchup", "NEXT RELEVANT", "stateCopy(feature)"):
        assert token in MENU
    assert "snapshot.browse?.nhl" in MENU
    assert "function renderNhl(list)" in MENU
    assert "No followed-team games are scheduled." in MENU
    assert "sourceStatus" in MENU and "broadcast" in MENU


def test_nhl_matchup_contract_deduplicates_composition_and_scopes_heading_focus():
    for token in (
        "const nhlMatchupName",
        "const nhlStatus",
        "hour12:true",
        "!value || /scheduled|upcoming/i.test(value)",
        "/\\d{1,2}\\/\\d{1,2}|\\b\\d{1,2}:\\d{2}\\b/.test(value)",
        "feature.detail || '', feature.broadcast || '', nhlStatus(feature)",
        "aria-label=\"${esc(matchupName)}\"",
        "const nhlLogo",
        "alt=\"${esc(nhlName(side, 'Team'))} logo\"",
        "aria-label=\"${esc(headingName)}\"",
        ".kiosk-section-head h1{display:inline-block;width:fit-content;max-width:100%}",
        ".kiosk-section-head h1:focus-visible",
    ):
        assert token in MENU or token in SCREENS
    assert "feature.subtitle || 'Followed-team game'" not in MENU
    assert "feature.sourceStatus || ''" not in MENU
    assert "onerror=\"this.remove()\"" in MENU


def test_calendar_contract_groups_and_limits_chronological_agenda():
    for token in ("agendaGroup", "Today", "Tomorrow", "This week", "agendaLimit", "max-width: 480px", "values.slice(1, 1 + agendaLimit())", "remaining", "kiosk-agenda-more", "is-birthday"):
        assert token in MENU


def test_calendar_full_agenda_contract_is_paginated_and_history_addressable():
    for token in (
        'data-calendar-disclosure', 'View all ${fullValues.length} events',
        'calendarMode = params.get(\'mode\') === \'all\'',
        'u.searchParams.set(\'mode\', \'all\')',
        'u.searchParams.set(\'page\', String(page))',
        'data-calendar-page', 'Page ${calendarPage} of ${settled ? pages : \'…\'}',
        'Back to summary', 'Return to Home', 'calendarPageSize',
        'measuredAgendaPageSize', 'aria-live="polite"',
        "e.key === 'ArrowLeft' || e.key === 'PageUp'",
        "e.key === 'ArrowRight' || e.key === 'PageDown'",
        "e.key === 'Escape' || e.key === 'BrowserBack'",
        'calendarDisclosure.focus({preventScroll: true})', "history.replaceState({marqueeCalendarAgenda: true}",
        'calendar-detail-surface',
    ):
        assert token in MENU
    for token in (
        '.kiosk-calendar-detail{', 'overflow:hidden',
        '.kiosk-calendar-controls button,.kiosk-calendar-controls a',
        'min-width:44px;min-height:44px',
    ):
        assert token in SCREENS
    assert 'more event${remaining === 1 ?' not in MENU
    assert 'remaining beyond this summary' not in MENU
    assert "document.fonts?.ready" in MENU
    assert "calendarLayoutSettlementScheduled" in MENU
    assert 'aria-busy="${settled ? \'false\' : \'true\'}"' in MENU


def test_calendar_focus_and_history_contracts_do_not_steal_control_focus():
    assert "function drawNavigation(preserveFocus = true)" in MENU
    assert "if (preserveFocus && focusedView !== undefined)" in MENU
    assert "document.addEventListener('focusin'" in MENU
    assert "const calendarHistoryChange = view === 'calendar' || nextView === 'calendar'" in MENU
    assert "drawNavigation(false)" in MENU
    assert "let calendarFocusHeadingPending = Boolean(calendarMode);" in MENU
    assert "let calendarFocusDisclosurePending = false;" in MENU
    assert "if (detail && calendarFocusHeadingPending)" in MENU
    assert "else if (detail && focusedCalendarControl)" in MENU
    assert "if (!detail && calendarFocusDisclosurePending && calendarDisclosure)" in MENU
    assert "if (preserveCalendarDisclosureFocus) calendarFocusDisclosurePending = true;" in MENU
    assert 'data-calendar-control="previous"' in MENU
    assert 'data-calendar-control="next"' in MENU
    assert "data-calendar-page]:not([disabled])" not in MENU
    assert "calendarFocusHeadingPending = true; calendarFocusDisclosurePending = false; history.pushState" in MENU
    assert "if (interrupted && !wasInterrupted && menu.open) closeMenu(false);" in MENU
    assert "history.back();" in MENU
    assert "function closeCalendarAgenda()" in MENU
    assert "calendarFocusDisclosurePending = true;\n    history.back();" in MENU
    assert "calendarFocusDisclosurePending = true; if (!(view === 'calendar' && !calendarMode)) calendarFocusDisclosurePending = false;" in MENU
    assert "setTimeout(() => calendarDisclosure?.focus" not in MENU
    assert "if (detail) panel.querySelector('#calendar-agenda-title')?.focus" not in MENU
    assert "mediaIdle" not in MENU
    assert "payload.playing === false" not in MENU


def test_calendar_fit_and_disclosure_contracts_use_real_geometry_and_touch_target():
    detail_start = MENU.index("function calendarDetail(list, options = {})")
    detail_end = MENU.index("function calendarLayoutKey", detail_start)
    assert "measuredAgendaPageSize" not in MENU[detail_start:detail_end]
    assert "settleCalendarLayout" in MENU
    assert "calendarPageFits(page)" in MENU
    assert "calendarPageSize === 1" in MENU
    assert "page.dataset.calendarOverflow = 'scroll'" in MENU
    assert "history.replaceState({marqueeCalendarAgenda: true}, '', href('calendar', true, calendarPage))" in MENU
    for token in (
        ".kiosk-agenda-more{display:inline-flex",
        "min-height:44px",
        "padding:10px 16px",
        "border:1px solid #b6f378",
        "cursor:pointer",
        ".kiosk-agenda-more:focus-visible",
    ):
        assert token in SCREENS


def test_overflow_trigger_and_escape_are_remote_visible_contracts():
    assert "activeInOverflow" in MENU
    assert "more.classList.toggle('is-active', activeInOverflow)" in MENU
    assert "current destination is ${label(view)}" in MENU
    assert "function updateCurrentDestination()" in MENU
    assert "document.querySelectorAll('.kiosk-rail a[data-view], .kiosk-menu a[data-view]').forEach(a => a.removeAttribute('aria-current'));" in MENU
    assert "const currentView = view || '';" in MENU
    assert "const direct = primary.querySelector(`[data-view=\"${CSS.escape(currentView)}\"]`);" in MENU
    assert "const active = direct && !direct.hidden ? direct : overflow.querySelector(`[data-view=\"${CSS.escape(currentView)}\"]`);" in MENU
    assert "more.removeAttribute('aria-current')" in MENU
    assert '<a href="/live">Live display</a>' in MENU
    assert "overflow.innerHTML = allDestinations().filter" in MENU
    assert "join(''); updateCurrentDestination();" in MENU
    assert 'aria-current="false"' not in MENU
    assert "aria-current=\"page\"" not in MENU
    assert "e.key === 'Escape' || e.key === 'BrowserBack'" in MENU
    assert "menu.addEventListener('cancel'" in MENU


def test_healthy_empty_states_do_not_offer_failure_retry():
    assert "The sky is quiet for now.', 'Return to Home', false, 'empty'" in MENU
    assert "`${label(view)} is quiet right now.`, 'Return to Home', false, 'empty'" in MENU
    assert "const combatView = key => key === 'ufc' || key === 'pfl';" in MENU
    assert "Checking the published ${promotion} schedule." in MENU
    assert "No upcoming ${combatName(view)} events are scheduled." in MENU
    assert "kiosk-state.is-resolved" in SCREENS
    assert "lifecycle.state, view)" in MENU
    assert "data-kiosk-retry" in MENU


def test_narrow_single_event_surfaces_remove_artificial_minimum_height():
    assert ".kiosk-sport-feature,.kiosk-editorial-feature{min-height:0" in SCREENS
    assert ".kiosk-support{margin-top:18px}" in SCREENS
    assert ".kiosk-more.is-active" in SCREENS


def test_editorial_renderer_exposes_the_authoritative_media_queue_and_safe_title_breaks():
    assert "queue.map((c, index)" in MENU
    assert "index === 0 ? 'Up next' : 'Later'" in MENU
    assert "c.detail || stateCopy(c)" in MENU
    assert "aria-label=\"${esc(label(view))} queue\"" in MENU
    assert ".kiosk-editorial-feature h2,.kiosk-sport-feature h2{overflow-wrap:break-word;word-break:normal;text-wrap:pretty" in SCREENS
    assert "const titleMarkup = text => esc(text).replace(/\\//g, '/<wbr>')" in MENU
    assert ".kiosk-section:is([data-section=gaming],[data-section=tv])" in SCREENS


def test_actual_kiosk_destinations_have_fixed_stage_geometry_contracts():
    for token in (
        ".kiosk-section[data-section=ufc] .kiosk-sports-layout{min-height:0}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial,\n  .kiosk-section[data-section=ufc] .kiosk-sports-layout{min-height:0}",
        ".kiosk-support{align-self:stretch;display:flex;flex-direction:column;justify-content:center",
    ):
        assert token in SCREENS


def test_kiosk_editorial_desktop_compaction_contract_is_deterministic():
    desktop = SCREENS.split("@media(min-width:901px)", 1)[1].split("@media", 1)[0]
    for token in (
        ".kiosk-section:is([data-section=gaming],[data-section=tv],[data-section=ufc]){padding:36px 44px}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial-feature{padding:40px}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv],[data-section=ufc]) :is(.kiosk-editorial-feature h2,.kiosk-sport-feature h2){font-size:clamp(56px,4.3vw,64px);line-height:1}",
    ):
        assert token in desktop


def test_shallow_landscape_contract_covers_secondary_17_10_and_keeps_decoration_out_of_scroll_geometry():
    assert "@media(min-width:1000px) and (max-height:700px) and (min-aspect-ratio:3/2)" in SCREENS
    assert ".kiosk-section.now-playing-surface{display:flex" in SCREENS
    assert "background:radial-gradient(circle,transparent 0 49%" in SCREENS
    shallow = SCREENS.rsplit("@media(min-width:1000px) and (max-height:700px) and (min-aspect-ratio:3/2)", 1)[1]
    assert ".kiosk-section:is([data-section=gaming],[data-section=tv]){display:flex;flex-direction:column;overflow:visible}" in shallow
    assert ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial{flex:1 1 auto;min-height:0;grid-template-rows:minmax(0,1fr)}" in shallow
    assert ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial-feature{height:100%;box-sizing:border-box;padding:16px}" in shallow
    assert "min-aspect-ratio: 3/2" in MENU


def test_kiosk_editorial_tablet_compaction_contract_is_deterministic():
    tablet = SCREENS.split("@media(min-width:481px) and (max-width:900px)", 1)[1].split("@media", 1)[0]
    for token in (
        ".kiosk-section:is([data-section=gaming],[data-section=tv]){padding:28px}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial-feature{padding:20px}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-editorial-feature h2{font-size:52px;line-height:1}",
        ".kiosk-section:is([data-section=gaming],[data-section=tv]) .kiosk-lede{font-size:20px;line-height:1.2}",
    ):
        assert token in tablet


def test_narrow_agenda_and_ufc_fit_contract_is_destination_scoped():
    for token in (
        ".kiosk-section[data-section=ufc]",
        ".kiosk-section[data-section=calendar]",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-feature{min-height:0",
        ".kiosk-section[data-section=ufc] .kiosk-sport-feature h2",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-more",
    ):
        assert token in SCREENS


def test_tablet_calendar_fit_contract_removes_feature_dead_space():
    tablet = SCREENS.split("@media(min-width:481px) and (max-width:700px)", 1)[1].split("@media", 1)[0]
    for token in (
        ".kiosk-section[data-section=calendar] .kiosk-agenda{gap:14px}",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-feature{min-height:0;justify-content:flex-start}",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-groups section{margin-bottom:14px}",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-row{padding:10px 0;gap:10px}",
        ".kiosk-section[data-section=calendar] .kiosk-agenda-more{margin:10px 0 0;font-size:14px}",
    ):
        assert token in tablet
    assert "@media(min-width:481px) and (max-width:700px)" in SCREENS
    assert "agendaLimit())" in MENU


def test_presentation_does_not_promote_raw_email_or_entity_source_names():
    assert "@/.test(value)" in MENU
    assert "Household calendar" in MENU
    assert "sourceLabel(c)" in MENU


def test_empty_and_unavailable_states_share_home_and_retry_actions():
    assert "sharedState(message" in MENU
    assert "data-kiosk-retry" in MENU
    assert "Return to Home" in MENU
    assert ".kiosk-state" in SCREENS


def test_destination_owns_background_accessibility_state_and_history_focus():
    assert "const backgroundNodes = [...document.body.children].filter(node => ![rail, menu, panel].includes(node));" in MENU
    assert "node.inert = true" in MENU
    assert "node.setAttribute('aria-hidden', 'true')" in MENU
    assert "if (ariaHidden === null) node.removeAttribute('aria-hidden');" in MENU
    assert "history.pushState({marqueeDestination: Boolean(key)}, '', href(key))" in MENU
    assert "primary.querySelector('[data-view=\"\"]')?.focus()" in MENU
    assert "panel.inert = !active || panel.hidden" in MENU


def test_weather_stage_is_the_authoritative_kiosk_surface_when_selected():
    for token in (
        "const stage = document.querySelector('.stage');",
        "surface = active && view === 'weather' && selected ? 'weather'",
        "const weatherActive = active && surface === 'weather';",
        "node === stage",
        "stage.classList.toggle('kiosk-covered', active && !weatherActive)",
        "stage.querySelector('#wx-segment-title')",
        "marquee-surface-rendered",
    ):
        assert token in MENU
    assert ".stage.kiosk-covered { display: none !important; }" in INDEX


def test_weather_controls_have_truthful_pressed_state_and_direct_heading_focus():
    weather = (ROOT / "output/weather-channel.js").read_text()
    assert '<h1 id="wx-segment-title" tabindex="-1">' in weather
    assert "aria-pressed=\"false\"" in weather
    assert "button.dataset.segment===segment" in weather
    assert "aria-pressed',String(paused)" in weather


def test_direct_destination_focus_is_pending_only_for_visible_initial_region():
    assert "let initialDirectFocusPending = Boolean(view);" in MENU
    assert "panel.setAttribute('aria-labelledby', 'kiosk-section-title')" in MENU
    assert "if (!initialDirectFocusPending || requestState === 'loading' || !view) return;" in MENU
    assert "heading.tabIndex = -1" in MENU
    assert "heading.focus({preventScroll: true})" in MENU
    assert "<h1 id=\"kiosk-section-title\">" in MENU
    assert "focusInitialDestination();" in MENU


def test_noninteractive_stage_headings_use_non_boxy_focus_without_weakening_controls():
    assert ".kiosk-section-head h1:focus-visible,.now-playing-surface .kiosk-now-playing-head h1:focus-visible" in SCREENS
    assert "outline:0;text-decoration-line:underline;text-decoration-style:dashed" in SCREENS
    assert ".kiosk-rail :focus-visible{outline:3px solid #c3fc86;outline-offset:2px}" in SCREENS
    assert ".kiosk-home-action:focus-visible,.kiosk-retry:focus-visible{outline:3px solid #fff;outline-offset:3px}" in SCREENS


def test_provider_error_stale_and_empty_states_have_distinct_deterministic_copy():
    assert "function destinationLifecycle(key, list)" in MENU
    assert "state: 'error'" in MENU
    assert "state: 'stale'" in MENU
    assert "state: list.length ? 'populated' : 'empty'" in MENU
    assert "The source did not answer. No last-known results are being presented as current." in MENU
    assert "The source has not refreshed. Last-known results are not being presented as current." in MENU
    assert "New items will appear automatically when this destination has something relevant." in MENU
    assert "data-lifecycle=\"${esc(lifecycle)}\"" in MENU
    assert "provider.state === 'degraded'" in MENU
    assert "data is delayed" in MENU


def test_pending_fetch_is_loading_without_failure_copy_or_retry():
    assert "let requestState = 'loading', requestSerial = 0" in MENU
    assert "requestState === 'loading'" in MENU
    assert "state: 'loading'" in MENU
    assert "Fetching the latest information for this destination." in MENU
    assert "lifecycle.state === 'loading' ? `Loading ${label(view)}…`" in MENU
    assert "lifecycle.state === 'error' || lifecycle.state === 'stale' || lifecycle.state === 'unavailable'" in MENU
    assert "if (refreshInFlight) return;" in MENU
    assert "if (serial !== requestSerial) return;" in MENU
    assert "requestState = resourceHasSnapshot() ? 'ready' : 'failed'" in MENU
    assert "data-lifecycle=\"${esc(lifecycle)}\"" in MENU


def test_responsive_contract_contains_dock_safe_containment_and_narrow_layouts():
    assert "inset:0 0 calc(8vh + var(--control-rail))" in SCREENS
    assert "@media(max-width:900px)" in SCREENS
    assert "@media(max-width:480px)" in SCREENS
    assert "overflow-x:hidden" in SCREENS
    assert ".kiosk-nhl-layout" in SCREENS


def test_short_wide_presentation_contract_is_scoped_and_summarizes_secondary_content():
    assert "@media(min-width:1000px) and (max-height:700px) and (min-aspect-ratio:3/2)" in SCREENS
    assert ".kiosk-section{overflow:hidden;padding:24px 44px}" in SCREENS
    assert ".kiosk-queue-row:nth-of-type(n+2){display:none}" in SCREENS
    assert ".kiosk-queue-more{display:block;margin:8px 0 0}" in SCREENS
    assert "const shortWide = () =>" in MENU
    assert "shortWide() ? 2 : 3" in MENU


def test_short_wide_sports_empty_state_keeps_action_reachable_with_readable_rhythm():
    shallow = SCREENS.rsplit(
        "@media(min-width:1000px) and (max-height:700px) and (min-aspect-ratio:3/2)", 1
    )[1]
    for token in (
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state{align-items:flex-start;gap:20px;margin-top:18px}",
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state-mark{width:64px;height:64px;font-size:48px}",
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state h2{font-size:clamp(32px,3.2vw,42px);line-height:1.05}",
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state .kiosk-empty{margin:8px 0;font-size:20px;line-height:1.25}",
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state .kiosk-now-playing-actions{margin-top:12px}",
        ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-home-action,\n  .kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-retry{box-sizing:border-box}",
    ):
        assert token in shallow
    assert ".kiosk-home-action,.kiosk-retry{display:inline-flex" in SCREENS
    assert "min-height:48px" in SCREENS
    assert "No upcoming ${combatName(view)} events are scheduled." in MENU
    assert "No games or fights are on the board." not in MENU
    assert "Return to Home" in MENU
    assert "(min-width: 1000px)" in MENU


def test_ufc_short_wide_empty_heading_avoids_fractional_scroll_rounding():
    shallow = SCREENS.rsplit(
        "@media(min-width:1000px) and (max-height:700px) and (min-aspect-ratio:3/2)", 1
    )[1]
    assert ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-state h2{font-size:clamp(32px,3.2vw,42px);line-height:1.05}" in shallow
    assert "/* UFC's two-line empty heading otherwise gets a fractional 1.05 line box;" in shallow
    assert ".kiosk-section[data-section=ufc] .kiosk-state h2{line-height:1}" in shallow
    assert ".kiosk-section[data-section=ufc] .kiosk-state h2{line-height:1}" not in shallow.split(".kiosk-section[data-section=ufc] .kiosk-state h2{line-height:1}", 1)[0]
    assert ".kiosk-section:is([data-section=ufc],[data-section=pfl]) .kiosk-home-action" in shallow
    assert "min-height:48px" in SCREENS
