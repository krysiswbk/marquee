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
    for token in ("agendaGroup", "Today", "Tomorrow", "This week", "values.slice(1, 9)", "is-birthday"):
        assert token in MENU


def test_presentation_does_not_promote_raw_email_or_entity_source_names():
    assert "@/.test(value)" in MENU
    assert "Household calendar" in MENU
    assert "sourceLabel(c)" in MENU


def test_empty_and_unavailable_states_share_home_and_retry_actions():
    assert "sharedState(message" in MENU
    assert "data-kiosk-retry" in MENU
    assert "Return to Home" in MENU
    assert ".kiosk-state" in SCREENS


def test_provider_error_stale_and_empty_states_have_distinct_deterministic_copy():
    assert "function destinationLifecycle(key, list)" in MENU
    assert "state: 'error'" in MENU
    assert "state: 'stale'" in MENU
    assert "state: list.length ? 'populated' : 'empty'" in MENU
    assert "The source did not answer. No last-known results are being presented as current." in MENU
    assert "The source has not refreshed. Last-known results are not being presented as current." in MENU
    assert "New items will appear automatically when this destination has something relevant." in MENU
    assert "data-lifecycle=\"${esc(lifecycle)}\"" in MENU


def test_responsive_contract_contains_dock_safe_containment_and_narrow_layouts():
    assert "inset:0 0 calc(8vh + var(--control-rail))" in SCREENS
    assert "@media(max-width:900px)" in SCREENS
    assert "@media(max-width:480px)" in SCREENS
    assert "overflow-x:hidden" in SCREENS
