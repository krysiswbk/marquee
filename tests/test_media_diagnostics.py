"""Provider diagnostics must report actual poll failures and usable timestamps."""
import json
import time
from datetime import datetime, timezone
from unittest.mock import patch
from cast.marquee.api import http


def test_media_failure_diagnostics_are_not_reported_healthy():
    state = dict(info=None, last_attempt=1789740000, last_success=1789739900,
                 error='Plex unavailable', stale=True)
    with patch.multiple(http, create=True, json=json, time=time, datetime=datetime,
                        timezone=timezone, CURRENT_PLEX=state,
                        PROVIDER_ENGINE={'value': None},
                        best_context=lambda *args: None), \
            patch.object(http, 'authorize', return_value=True), \
            patch.object(http, 'attention_route', return_value=False):
        handler = object.__new__(http.WebHandler)
        handler.path = '/providers'
        replies = []
        handler._send = lambda body, *args: replies.append(json.loads(body))
        handler.do_GET()
    status = replies[0]['providers']['plex']
    assert status['state'] == 'error'
    assert status['stale'] and status['error'] == 'Plex unavailable'
    assert datetime.fromisoformat(status['lastSuccess']).timestamp() == state['last_success']
    assert status['eligibleContexts'] == 0
