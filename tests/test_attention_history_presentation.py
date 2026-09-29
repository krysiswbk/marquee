"""Deterministic contracts for the responsive attention-history presentation."""

import json
import subprocess
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


def test_history_disclosure_names_distinguish_same_time_events() -> None:
    start = SCRIPT.index("  function humanize")
    end = SCRIPT.index("  function renderHistory")
    helper = SCRIPT[start:end]
    events = [
        {
            "at": 1800000000, "kind": "Transition", "source": "attention-rule",
            "id": "kitchen-1", "display": "hallway", "state": "NEW",
        },
        {
            "at": 1800000000, "kind": "Transition", "source": "attention-rule",
            "id": "kitchen-1", "display": "hallway", "state": "SUPPRESSED",
        },
        {
            "at": 1800000000, "kind": "signal", "source": "sensor.garage",
            "id": "garage-1", "state": "active",
        },
    ]
    script = f"events = {json.dumps(events)};\n{helper}\nconsole.log(JSON.stringify(events.map(item => historyDisclosureLabel(item, 'same timestamp'))));"
    result = subprocess.run(
        ["node", "-e", script], text=True,
        capture_output=True, check=True,
    )
    labels = json.loads(result.stdout)
    assert len(set(labels)) == len(events)
    assert labels[0] == (
        "View full payload for Transition — source attention-rule · id kitchen-1 "
        "· display hallway · state NEW at same timestamp"
    )
    assert labels[1] == (
        "View full payload for Transition — source attention-rule · id kitchen-1 "
        "· display hallway · state SUPPRESSED at same timestamp"
    )
    assert "state active" in labels[2]
    assert "source sensor.garage" in labels[2]
    assert "id garage-1" in labels[2]


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


def test_active_attention_uses_human_facing_labels_without_scores() -> None:
    assert "urgencyLabels" in SCRIPT
    assert "Action needed" in SCRIPT
    assert "item.score" not in SCRIPT
    assert "CONTEXTUAL · -5" not in SCRIPT
