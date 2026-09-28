import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MENU = (ROOT / "output/kiosk-menu.js").read_text()
SCREENS = (ROOT / "output/screens.css").read_text()
INDEX = (ROOT / "output/index.html").read_text()


class KioskNowPlayingSurfaceContractTests(unittest.TestCase):
    def test_plex_uses_the_authoritative_payload_for_every_lifecycle_state(self):
        self.assertIn("nowPlaying = payload", MENU)
        self.assertIn("view === 'plex'", MENU)
        self.assertIn("nowPlaying?.playing === true", MENU)
        self.assertIn("nowPlaying?.state === 'unavailable'", MENU)
        self.assertIn("Nothing is playing", MENU)
        self.assertIn("Media service unavailable", MENU)
        self.assertIn("state:'idle'", MENU)
        # No selected browse item may replace an authoritative Plex response.
        self.assertIn("if (interrupted || !view || view === 'plex') return payload", MENU)

    def test_idle_unavailable_surface_does_not_reuse_media_identity(self):
        self.assertIn("No previous title or artwork is retained here", MENU)
        self.assertNotIn("nowPlaying.title", MENU)
        self.assertNotIn("nowPlaying.key", MENU)
        self.assertIn("data-kiosk-retry", MENU)

    def test_navigation_and_touch_contract(self):
        self.assertIn('class="kiosk-home-action"', MENU)
        self.assertIn("e.key === 'Escape'", MENU)
        self.assertIn("change('')", MENU)
        self.assertIn("min-height:48px", SCREENS)
        self.assertIn("Return to Home", MENU)

    def test_responsive_surface_and_cache_identity(self):
        self.assertIn(".kiosk-section.now-playing-surface", SCREENS)
        self.assertIn("@media(max-width:700px)", SCREENS)
        self.assertIn("@media(max-width:480px)", SCREENS)
        self.assertIn("kiosk-menu.js?v=2.10.10", INDEX)


if __name__ == "__main__":
    unittest.main()
