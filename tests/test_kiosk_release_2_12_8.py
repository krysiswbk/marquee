from pathlib import Path

from integrations.homeassistant.marquee_popup_style import POPUP_STYLE, popup_content

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


def test_kiosk_launch_uses_ha_recovery_automation():
    assert 'title="Marquee"' not in SOURCES
    assert SOURCES.count('"input_button/press"') == 2
    assert SOURCES.count('entity_id="input_button.marquee_show_kiosk_overlay"') == 2
    assert "--popup-min-height:100dvh" in POPUP_STYLE
    content = popup_content("http://marquee/kiosk?v=release")
    assert '<iframe title="Marquee" src="about:blank"' in content
    assert "Date.now()" in content
    assert "open=" in content
    assert 'aria-label="Close Marquee"' in content
    assert "window.browser_mod.closePopup({tag:'marquee'})" in content
