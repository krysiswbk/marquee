import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INDEX = (ROOT / "output/index.html").read_text()


class CastSettingsRefreshContractTests(unittest.TestCase):
    def test_cast_uses_settings_endpoint_and_recovers_visible_error(self):
        self.assertIn("const settingsUrl = LIVE_SURFACE\n    ? '/live-settings.json' : '/settings.json';", INDEX)
        self.assertIn("settings request failed (${settingsResponse.status})", INDEX)
        self.assertIn(
            "Configuration refresh failed. Showing the last saved settings; retrying.",
            INDEX,
        )
        self.assertIn("window.MarqueeLifecycle.status('');", INDEX)
        self.assertLess(
            INDEX.index("window.MarqueeLifecycle.status('');"),
            INDEX.index("Configuration refresh failed."),
        )


if __name__ == "__main__":
    unittest.main()
