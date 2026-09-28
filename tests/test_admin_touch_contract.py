"""Deterministic source contracts for the administration touch/numeric batch."""

import re
from pathlib import Path

from cast.marquee.attention.schema import FORM_SCHEMA

ROOT = Path(__file__).parents[1]
SURFACES = {
    "/settings": ROOT / "cast/settings-control.html",
    "/settings/layout?profile=cast": ROOT / "cast/cast-layout.html",
    "/settings/layout?profile=live": ROOT / "cast/live-layout.html",
    "/settings/attention": ROOT / "cast/attention-settings.html",
    "/settings/tests": ROOT / "cast/display-tests.html",
}


def numeric_controls(source: str) -> list[str]:
    return re.findall(r"<input\b[^>]*\btype=[\"'](?:number|range)[\"'][^>]*>", source, re.I)


def test_every_in_scope_surface_loads_the_shared_contract() -> None:
    contract = (ROOT / "output/control-touch-contract.css").read_text()
    assert "min-height:44px" in contract
    for route, path in SURFACES.items():
        source = path.read_text()
        assert "/control-touch-contract.css?v=2.10.76" in source, route
        assert "min-height:44px" in contract


def test_static_numeric_controls_have_truthful_bounds_steps_and_descriptions() -> None:
    for route, path in SURFACES.items():
        source = path.read_text()
        association_source = source + ((ROOT / "output/settings-control.js").read_text() if route == "/settings" else "")
        for control in numeric_controls(source):
            assert re.search(r"\bmin=[\"'][^\"']+[\"']", control), (route, control)
            assert re.search(r"\bmax=[\"'][^\"']+[\"']", control), (route, control)
            assert re.search(r"\bstep=[\"'][^\"']+[\"']", control), (route, control)
            assert "aria-describedby=" in control or "querySelectorAll('input[type=\"number\"], input[type=\"range\"]')" in association_source, (route, control)


def test_attention_schema_and_editor_share_all_numeric_semantics() -> None:
    source = (ROOT / "output/attention-settings.js").read_text()
    for key, rule in FORM_SCHEMA.items():
        assert key in source
        assert "rule.min" in source and "rule.max" in source
        assert rule["min"] is not None and rule["max"] is not None
    assert "Allowed: ${rule.min}–${rule.max}" in source
    assert "aria-describedby" in source
    assert "aria-invalid" in source


def test_main_settings_model_ranges_are_explicit() -> None:
    source = (ROOT / "cast/settings-control.html").read_text()
    expected = {
        "display-width": ("320", "3840", "1"),
        "display-height": ("240", "2160", "1"),
        "rotation-seconds": ("5", "3600", "1"),
        "minimum-seconds": ("0", "600", "1"),
        "transition-ms": ("0", "5000", "1"),
        "relevance": ("0", "100", "1"),
    }
    for field, (low, high, step) in expected.items():
        match = re.search(rf'<input\b[^>]*\bid="{field}"[^>]*>', source)
        assert match, field
        tag = match.group(0)
        assert f'min="{low}"' in tag and f'max="{high}"' in tag and f'step="{step}"' in tag
