"""Home Assistant kiosk wrapper and one-time navigation popup."""

from html import escape
from pathlib import Path

from marquee_popup_style import POPUP_STYLE

BROWSER_ID = "a38e5c41-b99f0451"
WRAPPER_PATH = "/local/kiosk-marquee.html"
WRAPPER_SOURCE = Path(__file__).with_name("kiosk_marquee_wrapper.html")


def redirect_popup_data():
    """Leave the HA popup immediately so Firefox can unload it fully."""
    onload = (
        "if(!this.dataset.marqueeRedirect){this.dataset.marqueeRedirect='1';"
        f"window.top.location.href='{WRAPPER_PATH}?open='+Date.now()}}"
    )
    content = (
        '<iframe title="Opening Marquee" src="about:blank" '
        f'onload="{escape(onload, quote=True)}" '
        'style="position:fixed;inset:0;width:100vw;height:100dvh;border:0"></iframe>'
        f'<a href="{WRAPPER_PATH}" '
        'style="position:fixed;left:24px;bottom:24px;z-index:2;color:white">'
        'Open Marquee</a>'
    )
    return {
        "browser_id": [BROWSER_ID],
        "dismissable": True,
        "tag": "marquee",
        "initial_style": "marquee-fullscreen",
        "style_sequence": ["marquee-fullscreen"],
        "popup_styles": [{
            "style": "marquee-fullscreen",
            "include_styles": ["fullscreen"],
            "styles": POPUP_STYLE,
        }],
        "content": content,
    }
