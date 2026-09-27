"""Optional AppDaemon producer: HA owns state, Marquee owns attention.

apps.yaml:
  marquee_attention:
    module: marquee_attention
    class: MarqueeAttention
    marquee_url: http://MARQUEE:8084

The server's declarative bindings determine the entity allowlist. Existing HA
rules and automations need no changes. A full snapshot also removes vanished
entities. Never forward HA access tokens to Marquee.
"""
import datetime
import time

import appdaemon.plugins.hass.hassapi as hass
import requests
from marquee_bridge import BridgeSession


class MarqueeAttention(hass.Hass):
    def initialize(self):
        self.bridge = BridgeSession()
        self.url = self.args["marquee_url"].rstrip("/")
        self.listeners = {}
        self.entities = set()
        self.last_error = None
        self.next_refresh = 0
        self.run_every(self.snapshot, "now", 1)

    def changed(self, entity, attribute, old, new, kwargs):
        self.next_refresh = 0

    def snapshot(self, kwargs):
        if time.time() < self.next_refresh:
            return
        try:
            response = self.bridge.get(self.url + "/api/attention/bindings", timeout=5)
            response.raise_for_status()
            manifest = response.json()
            entities = set(manifest["entities"])
            for entity in self.entities - entities:
                self.cancel_listen_state(self.listeners.pop(entity))
            for entity in entities - self.entities:
                self.listeners[entity] = self.listen_state(self.changed, entity, attribute="all")
            self.entities = entities
            states = []
            for entity in sorted(entities):
                value = self.get_state(entity, attribute="all")
                if value:
                    # Only display-relevant metadata, not arbitrary HA attributes.
                    attrs = value.get("attributes", {})
                    states.append({"entity_id": entity, "state": str(value["state"]),
                                   "attributes": {key: attrs[key] for key in
                                                  manifest.get("attributes", ["friendly_name"])
                                                  if key in attrs}})
            result = self.bridge.post(self.url + "/api/attention/signals", json={
                "states": states, "full": True,
                "observed_at": datetime.datetime.now(datetime.timezone.utc).timestamp()}, timeout=5)
            result.raise_for_status()
            self.next_refresh = time.time() + min(30, manifest["refresh_seconds"])
            if self.last_error:
                self.log("Marquee attention source recovered")
            self.last_error = None
            self.set_state("sensor.marquee_attention_bridge", state="connected", attributes={
                "friendly_name": "Marquee household connection", "icon": "mdi:home-assistant",
                "configured_entities": len(entities), "published_entities": len(states),
                "unavailable_entities": [s["entity_id"] for s in states
                                         if s["state"] in ("unknown", "unavailable")],
                "last_success": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        except (requests.RequestException, ValueError, KeyError) as error:
            message = str(error)
            if message != self.last_error:
                self.log("Marquee attention source unavailable: " + message, level="WARNING")
            self.last_error = message
            self.next_refresh = time.time() + 5
            self.set_state("sensor.marquee_attention_bridge", state="disconnected", attributes={
                "friendly_name": "Marquee household connection", "icon": "mdi:lan-disconnect",
                "error": message})
