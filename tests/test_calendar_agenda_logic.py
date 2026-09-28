"""Executable contracts for Calendar page fitting and history transitions."""

from pathlib import Path


MENU = (Path(__file__).parents[1] / "output/kiosk-menu.js").read_text()


def fit_page_size(initial: int, client_height: int, rendered_heights: dict[int, int]) -> int:
    """Model the bounded DOM-measure/decrement loop used by the renderer."""
    size = max(1, initial)
    while size > 1 and rendered_heights[size] > client_height + 1:
        size -= 1
    return size


def test_representative_pages_decrement_until_the_rendered_page_fits() -> None:
    assert fit_page_size(3, 183, {3: 259, 2: 170, 1: 100}) == 2
    assert fit_page_size(4, 155, {4: 278, 3: 205, 2: 140, 1: 80}) == 2
    assert fit_page_size(6, 333, {6: 404, 5: 350, 4: 300, 3: 230}) == 4
    assert fit_page_size(4, 300, {4: 278, 3: 210}) == 4


def test_fit_loop_terminates_at_one_row_even_when_content_is_tall() -> None:
    assert fit_page_size(6, 40, {6: 400, 5: 330, 4: 260, 3: 190, 2: 120, 1: 60}) == 1
    assert "calendarPageSize > 1" in MENU


def test_page_canonicalization_and_history_model_are_summary_first() -> None:
    history = ["home", "calendar-summary", "calendar-all?page=1"]
    history[-1] = "calendar-all?page=3"  # replaceState pagination
    assert history.pop() == "calendar-all?page=3"
    assert history[-1] == "calendar-summary"
    assert "history.replaceState({marqueeCalendarAgenda: true}" in MENU
    assert "history.back();" in MENU
    assert "history.replaceState({marqueeDestination: true}, '', href('calendar'))" not in MENU


def test_focus_restoration_is_explicit_or_logical_control_preserving() -> None:
    assert "calendarFocusHeadingPending" in MENU
    assert "focusedCalendarControl" in MENU
    assert 'data-calendar-control="previous"' in MENU
    assert 'data-calendar-control="next"' in MENU
    assert "data-calendar-page]:not([disabled])" not in MENU
