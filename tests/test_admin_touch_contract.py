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
        assert "/control-touch-contract.css?v=2.10.86" in source, route
        assert "min-height:44px" in contract


def test_every_numeric_surface_loads_one_helper_before_its_consumers() -> None:
    helper = "/numeric-controls.js?v=2.10.86"
    for route, path in SURFACES.items():
        source = path.read_text()
        assert source.count(helper) == 1, route
        assert "window.MarqueeNumericControls" in (ROOT / "output/numeric-controls.js").read_text()
        helper_position = source.index(helper)
        if route == "/settings":
            assert "/control-shell.js" not in source
            assert helper_position < source.index("/settings-control.js"), route
        else:
            assert helper_position < source.index("/control-shell.js"), route


def test_static_numeric_controls_have_truthful_bounds_steps_and_descriptions() -> None:
    for route, path in SURFACES.items():
        source = path.read_text()
        association_source = source + (ROOT / "output/numeric-controls.js").read_text()
        association_source += (ROOT / "output/control-shell.js").read_text()
        if route == "/settings":
            association_source += (ROOT / "output/settings-control.js").read_text()
        for control in numeric_controls(source):
            assert re.search(r"\bmin=[\"'][^\"']+[\"']", control), (route, control)
            assert re.search(r"\bmax=[\"'][^\"']+[\"']", control), (route, control)
            assert re.search(r"\bstep=[\"'][^\"']+[\"']", control), (route, control)
            assert "aria-describedby=" in control or "querySelectorAll('input[type=\"number\"], input[type=\"range\"]')" in association_source, (route, control)


def test_static_numeric_controls_have_names_and_explicit_range_context() -> None:
    for route, path in SURFACES.items():
        source = path.read_text()
        for control in numeric_controls(source):
            control_id = re.search(r'\bid=["\']([^"\']+)["\']', control, re.I)
            named = ('aria-label=' in control or 'aria-labelledby=' in control
                     or 'data-backdrop-field=' in control or 'data-layout-field=' in control
                     or (control_id and re.search(rf'<label\b[^>]*for=["\']{re.escape(control_id.group(1))}["\']', source, re.I)))
            assert named, (route, control)
            assert re.search(r'\bmin=["\'][^"\']+["\']', control) and re.search(r'\bmax=["\'][^"\']+["\']', control), (route, control)
            assert 'aria-describedby=' in control or 'numeric-help' in source, (route, control)


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
