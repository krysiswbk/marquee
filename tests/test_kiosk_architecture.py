from pathlib import Path


ROOT = Path(__file__).parents[1]
MENU = (ROOT / "output/kiosk-menu.js").read_text()
SCREENS = (ROOT / "output/screens.css").read_text()


def test_forced_destinations_have_purposeful_category_renderers():
    for name in ("categoryFor", "renderSports", "renderAgenda", "renderMedia", "renderAmbient"):
        assert name in MENU
    assert "sportViews" in MENU and "mediaViews" in MENU
    assert "renderDestination(view, list)" in MENU


def test_sports_contract_keeps_matchup_status_and_next_event_hierarchy():
    for token in ("kiosk-sport-feature", "kiosk-matchup", "NEXT RELEVANT", "stateCopy(feature)"):
        assert token in MENU


def test_calendar_contract_groups_and_limits_chronological_agenda():
    for token in ("agendaGroup", "Today", "Tomorrow", "This week", "agendaLimit", "max-width: 480px", "values.slice(1, 1 + agendaLimit())", "remaining", "kiosk-agenda-more", "is-birthday"):
        assert token in MENU


def test_overflow_trigger_and_escape_are_remote_visible_contracts():
    assert "activeInOverflow" in MENU
    assert "more.classList.toggle('is-active', activeInOverflow)" in MENU
    assert "current destination is ${label(view)}" in MENU
    assert "aria-current', activeInOverflow ? 'page' : 'false'" in MENU
    assert "e.key === 'Escape' && view && !menu.open" in MENU
    assert "menu.addEventListener('cancel'" in MENU


def test_healthy_empty_states_do_not_offer_failure_retry():
    assert "The sky is quiet for now.', 'Return to Home', false, 'empty'" in MENU
    assert "`${label(view)} is quiet right now.`, 'Return to Home', false, 'empty'" in MENU
    assert "No games or fights are on the board.', 'Return to Home', false, 'empty'" in MENU
    assert "lifecycle.state)" in MENU
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
    assert ".kiosk-editorial-feature h2,.kiosk-sport-feature h2{overflow-wrap:anywhere" in SCREENS
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


def test_direct_destination_focus_is_pending_only_for_visible_initial_region():
    assert "let initialDirectFocusPending = Boolean(view);" in MENU
    assert "panel.setAttribute('aria-labelledby', 'kiosk-section-title')" in MENU
    assert "if (!initialDirectFocusPending || requestState === 'loading' || !view || panel.hidden || panel.inert) return;" in MENU
    assert "heading.tabIndex = -1" in MENU
    assert "heading.focus({preventScroll: true})" in MENU
    assert "<h1 id=\"kiosk-section-title\">" in MENU
    assert "focusInitialDestination();" in MENU


def test_provider_error_stale_and_empty_states_have_distinct_deterministic_copy():
    assert "function destinationLifecycle(key, list)" in MENU
    assert "state: 'error'" in MENU
    assert "state: 'stale'" in MENU
    assert "state: list.length ? 'populated' : 'empty'" in MENU
    assert "The source did not answer. No last-known results are being presented as current." in MENU
    assert "The source has not refreshed. Last-known results are not being presented as current." in MENU
    assert "New items will appear automatically when this destination has something relevant." in MENU
    assert "data-lifecycle=\"${esc(lifecycle)}\"" in MENU


def test_pending_fetch_is_loading_without_failure_copy_or_retry():
    assert "let requestState = 'loading', requestSerial = 0" in MENU
    assert "requestState === 'loading'" in MENU
    assert "state: 'loading'" in MENU
    assert "Fetching the latest information for this destination." in MENU
    assert "lifecycle.state === 'loading' ? `Loading ${label(view)}…`" in MENU
    assert "lifecycle.state === 'error' || lifecycle.state === 'stale' || lifecycle.state === 'unavailable'" in MENU
    assert "if (requestState === 'loading' && requestSerial > 0) return;" in MENU
    assert "if (serial !== requestSerial) return;" in MENU
    assert "requestState = 'ready'" in MENU
    assert "requestState = 'failed'" in MENU
    assert "data-lifecycle=\"${esc(lifecycle)}\"" in MENU


def test_responsive_contract_contains_dock_safe_containment_and_narrow_layouts():
    assert "inset:0 0 calc(8vh + var(--control-rail))" in SCREENS
    assert "@media(max-width:900px)" in SCREENS
    assert "@media(max-width:480px)" in SCREENS
    assert "overflow-x:hidden" in SCREENS


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
    assert "No games or fights are on the board." in MENU
    assert "New items will appear automatically when this destination has something relevant." in MENU
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
