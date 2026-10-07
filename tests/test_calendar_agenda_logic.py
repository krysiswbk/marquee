"""Executable contracts for the continuous, scrollable Calendar agenda."""

from pathlib import Path


MENU = (Path(__file__).parents[1] / "output/kiosk-menu.js").read_text()
SCREENS = (Path(__file__).parents[1] / "output/screens.css").read_text()


def test_full_agenda_renders_every_entry_in_one_scrollable_date_grouped_list() -> None:
    assert "function calendarDetail(list)" in MENU
    assert "list.reduce((map, c) => { const key = agendaGroup(dateOf(c))" in MENU
    assert "values.map(calendarRow).join('')" in MENU
    assert 'class="kiosk-agenda-groups kiosk-calendar-page" tabindex="0"' in MENU
    assert "${list.length} ${list.length === 1 ? 'event' : 'events'}" in MENU
    assert ".kiosk-calendar-page{min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain" in SCREENS
    assert "data-calendar-control" not in MENU
    assert "calendarPage" not in MENU


def test_agenda_history_and_focus_return_to_the_existing_summary() -> None:
    assert "calendarMode = params.get('mode') === 'all'" in MENU
    assert "u.searchParams.set('mode', 'all'); u.searchParams.delete('page')" in MENU
    assert "Back to summary" in MENU
    assert "history.back();" in MENU
    assert "calendarDisclosure.focus({preventScroll: true})" in MENU
    assert "calendarFocusHeadingPending" in MENU
