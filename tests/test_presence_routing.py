import unittest

from cast.marquee.core.presence import PresenceGate, bedroom_eligible


class PresenceRoutingTests(unittest.TestCase):
    def test_bedroom_sleep_and_cutoff_are_absolute_vetoes(self):
        self.assertTrue(bedroom_eligible(True, False, False, 21, 59))
        self.assertFalse(bedroom_eligible(True, True, False, 21, 59))
        self.assertFalse(bedroom_eligible(True, False, True, 21, 59))
        self.assertFalse(bedroom_eligible(True, False, False, 22, 0))

    def test_activation_debounce_and_release_grace(self):
        gate = PresenceGate(activation_seconds=15, release_seconds=30)
        self.assertFalse(gate.update(True, 100))
        self.assertFalse(gate.update(True, 114))
        self.assertTrue(gate.update(True, 115))
        self.assertTrue(gate.update(False, 120))
        self.assertTrue(gate.update(False, 149))
        self.assertFalse(gate.update(False, 150))

    def test_absolute_veto_releases_immediately(self):
        gate = PresenceGate(activation_seconds=0, release_seconds=30)
        self.assertTrue(gate.update(True, 100))
        self.assertFalse(gate.update(False, 101, absolute_veto=True))
