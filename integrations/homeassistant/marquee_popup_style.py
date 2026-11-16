"""Browser Mod popup markup shared by the kiosk launch paths."""

import json
from html import escape

POPUP_STYLE = (
    'ha-dialog{--ha-dialog-surface-background:#000;--ha-dialog-border-radius:0;'
    '--dialog-content-padding:0;--padding-x:0;--padding-y:0;'
    '--popup-min-height:100dvh;--popup-max-height:100dvh}'
    'ha-dialog .content,ha-dialog .content .container{'
    'margin:0!important;padding:0!important}'
)


def popup_content(url: str) -> str:
    """Fill the viewport and load a fresh iframe when Firefox reopens the popup."""
    onload = (
        "if(!this.dataset.marqueeLoaded){this.dataset.marqueeLoaded='1';"
        f"this.src={json.dumps(url + ('&' if '?' in url else '?') + 'open=')}+Date.now()}}"
    )
    return (
        '<iframe title="Marquee" src="about:blank" '
        f'onload="{escape(onload, quote=True)}" '
        'style="display:block;position:fixed;inset:0;width:100vw;'
        'height:100dvh;border:0;z-index:1"></iframe>'
        '<button type="button" aria-label="Close Marquee" title="Close Marquee" '
        'style="position:fixed;top:10px;right:10px;width:56px;height:56px;'
        'border:0;border-radius:50%;background:rgba(0,0,0,.78);'
        'color:#fff;font-size:32px;z-index:1000" '
        'onclick="window.browser_mod.closePopup({tag:\'marquee\'})">'
        '&times;</button>'
    )
