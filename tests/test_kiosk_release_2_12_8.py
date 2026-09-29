from pathlib import Path


ROOT = Path(__file__).parents[1]
INDEX = (ROOT / "output/index.html").read_text()
SOURCES = "\n".join(
    (ROOT / name).read_text()
    for name in (
        "integrations/homeassistant/marquee_sources.py",
        "integrations/homeassistant/marquee_ambient.py",
    )
)


def test_context_replacement_is_committed_before_any_transition_timer():
    replacement = INDEX.index("render(d);\n      refreshPoster(d);", INDEX.index("if (key !== shownKey)"))
    assert INDEX.index("stage.classList.remove('fade');", replacement) < INDEX.index(
        "shownKey = key", replacement
    )
    assert "stage.classList.add('fade');" not in INDEX[INDEX.index("if (key !== shownKey)") : INDEX.index("shownKey = key")]


def test_browser_mod_popup_does_not_reserve_a_close_row():
    assert '"aspect_ratio"' not in SOURCES
    assert "height:100%!important" in SOURCES
    assert "width:56px!important" in SOURCES
    assert "env(safe-area-inset-top)" in SOURCES
    assert "ha-dialog-header button" in SOURCES
