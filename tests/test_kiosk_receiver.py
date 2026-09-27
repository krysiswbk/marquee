import os
import urllib.parse
from unittest.mock import patch
from cast.marquee.api import http


def test_receiver_routes_to_scaler_but_inner_page_is_the_real_kiosk():
    for path, expected in [('/kiosk?receiver=1&display=garage','kiosk-receiver.html'),
                           ('/kiosk?display=garage','index.html'),
                           ('/kiosk','index.html'),('/image','index.html'),
                           ('/kiosk?receiver=0','index.html')]:
        handler=object.__new__(http.WebHandler);handler.path=path
        sent=[];handler._send_file=sent.append
        with patch.multiple(http,create=True,OUTPUT='/display',os=os,urllib=urllib),patch.object(http,'attention_route',return_value=False),patch.object(http,'authorize',return_value=True):
            handler.do_GET()
        assert sent==['/display/'+expected]
