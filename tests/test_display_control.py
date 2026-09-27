import unittest
from datetime import datetime, timedelta, timezone
from cast.marquee.core.arbitration import ContextArbiter

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


class DisplayControlTests(unittest.TestCase):
    def setUp(self):
        self.arbiter = ContextArbiter(rotation_seconds=30, minimum_context_seconds=12)
        self.items = [{"id": name, "title": name, "priority": 50} for name in ['a', 'b', 'c']]

    def select(self, seconds=0, items=None, display='kiosk'):
        return self.arbiter.select(self.items if items is None else items, [], display=display,
                                   now=NOW + timedelta(seconds=seconds))

    def command(self, action, seconds=0):
        return self.arbiter.control(action, now=NOW + timedelta(seconds=seconds))

    def test_next_bypasses_dwell_and_previous_wraps(self):
        self.assertEqual(self.select()['id'], 'a')
        self.command('previous')
        self.assertEqual(self.select()['id'], 'c')
        self.command('next')
        self.assertEqual(self.select()['id'], 'a')

    def test_manual_step_has_full_interval_then_rotates(self):
        self.select(29)
        self.command('next', 29)
        self.assertEqual(self.select(30)['id'], 'b')
        self.assertEqual(self.select(58)['id'], 'b')
        self.assertEqual(self.select(60)['id'], 'c')

    def test_frozen_content_updates_and_arrows_keep_freeze(self):
        self.select()
        self.command('freeze')
        updated = [dict(item, detail='fresh score') for item in self.items]
        self.assertEqual(self.select(65, updated)['detail'], 'fresh score')
        self.assertEqual(self.select(65)['id'], 'a')
        self.command('next', 65)
        self.assertEqual(self.select(65)['id'], 'b')
        self.assertTrue(self.arbiter.control_state()['frozen'])
        self.command('resume', 65)
        self.assertEqual(self.select(65)['id'], 'c')
        self.assertFalse(self.arbiter.control_state()['frozen'])

    def test_expired_screen_releases_freeze(self):
        self.select()
        self.command('freeze')
        self.items[0]['expires'] = (NOW + timedelta(seconds=1)).isoformat()
        self.assertNotEqual(self.select(2)['id'], 'a')
        self.assertFalse(self.arbiter.control_state()['frozen'])

    def test_controls_do_not_change_hubs(self):
        self.select()
        self.command('next')
        self.assertEqual(self.select()['id'], 'b')
        self.assertIsNone(self.select(display='hubs'))

    def test_empty_single_and_invalid_actions(self):
        self.select(items=[])
        self.command('freeze')
        self.assertFalse(self.arbiter.control_state()['frozen'])
        self.select(items=self.items[:1])
        self.command('next')
        self.assertEqual(self.select(items=self.items[:1])['id'], 'a')
        with self.assertRaises(ValueError):
            self.command('delete')
        with self.assertRaises(ValueError):
            self.arbiter.control('next', display='hubs')
