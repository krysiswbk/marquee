"""Browser Mod popup styling shared by kiosk launch paths."""

POPUP_STYLE = (
    'ha-dialog{--ha-dialog-surface-background:#000;--ha-dialog-border-radius:0;'
    '--dialog-content-padding:0;--padding-x:0;--padding-y:0;'
    '--popup-min-height:100dvh;--popup-max-height:100dvh}'
    'ha-dialog .content{height:100dvh!important;min-height:0!important;overflow:hidden!important}'
    'ha-dialog .content .container{margin:0!important;padding:0!important;'
    'height:100%!important}'
)

IFRAME_CARD_STYLE = (
    'ha-card{border:0;box-shadow:none;height:100dvh!important}'
    '#root{padding-top:0!important;height:100dvh!important}'
    'iframe{height:100%!important}'
)

CLOSE_CARD_STYLE = (
    'ha-card{position:fixed!important;top:max(10px,env(safe-area-inset-top))!important;'
    'right:max(10px,env(safe-area-inset-right))!important;left:auto!important;'
    'z-index:1000!important;width:56px!important;height:56px!important;'
    'min-width:56px!important;min-height:56px!important;'
    'border-radius:50%!important;background:rgba(0,0,0,.78)!important;'
    'box-shadow:none!important;padding:0!important;display:flex;'
    'align-items:center;justify-content:center;'
    '--state-color:#fff!important;--state-icon-color:#fff!important}'
    'ha-state-icon{width:28px!important;height:28px!important;color:#fff!important}'
)


def popup_content(url: str, browser_id: str) -> dict:
    """Give the iframe viewport height and a separate close target over it."""
    return {
        "type": "vertical-stack",
        "cards": [
            {"type": "iframe", "url": url, "aspect_ratio": "66.67%",
             "card_mod": {"style": IFRAME_CARD_STYLE}},
            {"type": "button", "name": "Close Marquee", "icon": "mdi:close",
             "show_name": False,
             "tap_action": {"action": "perform-action",
                            "perform_action": "browser_mod.close_popup",
                            "data": {"browser_id": [browser_id], "tag": "marquee"}},
             "card_mod": {"style": CLOSE_CARD_STYLE}},
        ],
    }
