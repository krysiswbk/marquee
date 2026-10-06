import unittest

from cast.marquee.sky import clean_sky


class SkyContractTests(unittest.TestCase):
    def test_missing_sky_is_omitted(self):
        self.assertIsNone(clean_sky(None))
        self.assertIsNone(clean_sky({"moon": {"phase": ""}}))

    def test_valid_values_are_bounded_and_aircraft_need_position(self):
        result = clean_sky({"cloud_cover": 42, "visibility": 18000, "visibility_unit": "m",
                            "sun": {"is_day": False, "elevation": -8},
                            "moon": {"phase": "waning_crescent", "illumination": .21,
                                     "azimuth": 271, "elevation": 16},
                            "aircraft": [{"id": "adsb:ONE", "bearing": 240, "elevation": 12,
                                          "heading": 80}, {"id": "no-position"}]})
        self.assertEqual(result["cloud_cover"], 42)
        self.assertEqual(result["visibility_unit"], "m")
        self.assertFalse(result["sun"]["is_day"])
        self.assertEqual(result["moon"]["illumination"], .21)
        self.assertEqual(len(result["aircraft"]), 1)

    def test_out_of_range_facts_never_survive(self):
        self.assertIsNone(clean_sky({"cloud_cover": 101, "moon": {"illumination": 2}}))

    def test_phase_only_moon_remains_phase_only(self):
        result = clean_sky({"moon": {"phase": "waning_crescent"}})
        self.assertEqual(result, {"moon": {"phase": "waning_crescent"}})

    def test_legacy_open_meteo_visibility_defaults_to_its_configured_km_unit(self):
        self.assertEqual(clean_sky({"visibility": 24.4}),
                         {"visibility": 24.4, "visibility_unit": "km"})
