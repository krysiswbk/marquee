"""Deterministic contracts for the responsive attention-history presentation."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = (ROOT / "output" / "attention-settings.js").read_text()
STYLES = (ROOT / "output" / "settings-admin.css").read_text()
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "attention-history.json").read_text())


def test_fixture_covers_authoritative_unknown_and_long_history_fields() -> None:
    assert FIXTURE[0]["metadata"]["unknown_flag"] is True
    assert "long_value" in FIXTURE[0]
    assert FIXTURE[1]["state"] == "unavailable"


def test_history_has_human_summary_and_explicit_full_payload_disclosure() -> None:
    for token in (
        "historyAge", "historyFields", "history-kind", "history-source",
        "history-outcome", "history-summary", "View full event payload",
        "JSON.stringify(item, null, 2)", "aria-label",
    ):
        assert token in SCRIPT


def test_history_is_truthful_for_empty_invalid_error_and_large_sets() -> None:
    for token in (
        "No recent attention history.",
        "History is unavailable: the response did not contain a valid event list.",
        "History unavailable:",
        "HISTORY_PAGE_SIZE = 40",
        "Older events remain available.",
        "data.history_status === 'error'",
    ):
        assert token in SCRIPT


def test_history_layout_wraps_without_a_mobile_scrolling_table() -> None:
    assert ".history-row{display:grid" in STYLES
    assert "overflow-wrap:anywhere" in STYLES
    assert ".history-row{grid-template-columns:repeat(2,minmax(0,1fr))" in STYLES
    assert ".history-details{grid-column:1/-1}" in STYLES
