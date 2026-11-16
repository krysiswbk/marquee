from pathlib import Path

from integrations.homeassistant.marquee_popup_style import IFRAME_CARD_STYLE, POPUP_STYLE

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
    assert SOURCES.count('"styles": POPUP_STYLE') == 2
    assert SOURCES.count('"style": IFRAME_CARD_STYLE') == 2
    assert "ha-dialog .content{position:fixed!important;inset:0!important" in POPUP_STYLE
    assert 'ha-icon-button[slot="headerNavigationIcon"]{position:fixed!important' in POPUP_STYLE
    assert "env(safe-area-inset-top)" in POPUP_STYLE
    assert "#root{padding-top:0!important;height:100dvh!important}" in IFRAME_CARD_STYLE
