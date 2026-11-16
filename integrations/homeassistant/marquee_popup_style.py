"""Browser Mod popup styling shared by kiosk launch paths."""

POPUP_STYLE = (
    'ha-dialog{--ha-dialog-surface-background:#000;--ha-dialog-border-radius:0!important;'
    '--dialog-content-padding:0;--padding-x:0;--padding-y:0;'
    '--popup-min-height:100dvh;--popup-max-height:100dvh}'
    'ha-dialog .content{position:fixed!important;inset:0!important;z-index:1;'
    'width:100vw!important;height:100dvh!important;overflow:hidden!important}'
    'ha-dialog .content .container{margin:0!important;padding:0!important;'
    'width:100%!important;height:100%!important}'
    'ha-dialog ha-icon-button[slot="headerNavigationIcon"]{position:fixed!important;'
    'top:max(10px,env(safe-area-inset-top))!important;'
    'right:max(10px,env(safe-area-inset-right))!important;left:auto!important;'
    'z-index:50;width:56px;height:56px;border-radius:50%;'
    'background:rgba(0,0,0,.68)}.title{display:none!important}'
)

IFRAME_CARD_STYLE = (
    'ha-card{border:0;box-shadow:none;height:100dvh!important}'
    '#root{padding-top:0!important;height:100dvh!important}'
    'iframe{height:100%!important}'
)
