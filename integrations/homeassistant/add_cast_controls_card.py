"""Place the Marquee Cast buttons beside the existing Marquee cards."""
import asyncio
import os

import aiohttp


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("ws://supervisor/core/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth",
                                "access_token": os.environ["SUPERVISOR_TOKEN"]})
            await ws.receive_json()

            async def call(message_id, payload):
                await ws.send_json({"id": message_id, **payload})
                while True:
                    response = await ws.receive_json()
                    if response.get("id") == message_id:
                        if not response.get("success"):
                            raise RuntimeError(response)
                        return response.get("result")

            config = await call(1, {"type": "lovelace/config",
                                    "url_path": "lovelace"})
            cards = config["views"][0].setdefault("cards", [])
            title = "Marquee — Cast Displays"
            card = {
                "type": "entities", "title": title, "show_header_toggle": False,
                "entities": [
                    {"entity": "input_button.marquee_cast_main_display",
                     "name": "Main Display", "icon": "mdi:cast-connected"},
                    {"entity": "input_button.marquee_cast_garage_display",
                     "name": "Garage Display", "icon": "mdi:garage"},
                    {"entity": "input_button.marquee_cast_bedroom_display",
                     "name": "Bedroom Display", "icon": "mdi:bed"},
                ],
            }
            existing = next((item for item in cards if item.get("title") == title), None)
            if existing:
                existing.clear(); existing.update(card)
            else:
                anchor = next((i for i, item in enumerate(cards)
                               if item.get("title") == "Marquee — Configuration"),
                              len(cards) - 1)
                cards.insert(anchor + 1, card)
            await call(2, {"type": "lovelace/config/save", "url_path": "lovelace",
                           "config": config})
            print("Marquee Cast Displays card saved")


asyncio.run(main())
