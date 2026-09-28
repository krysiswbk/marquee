import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
INDEX = (ROOT / "output/index.html").read_text()


class PosterLifecycleContractTests(unittest.TestCase):
    def test_no_art_payloads_do_not_construct_poster_request(self):
        self.assertIn("if (!posterAvailable) {", INDEX)
        self.assertIn("clearPosterPresentation();", INDEX)
        self.assertIn("const posterAvailable = DEMO ? Boolean(demoM().poster) : d.poster === true;", INDEX)
        refresh = INDEX.split("function refreshPoster(d) {", 1)[1].split("\n  function fitSceneClocks", 1)[0]
        self.assertIn("if (!posterAvailable)", refresh)
        self.assertNotIn("i.src = '/poster.jpg", refresh)

    def test_real_media_art_keeps_authoritative_poster_contract(self):
        self.assertIn("const requestIdentity = `${d.key || ''}|${d.posterVersion || 'legacy'}`;", INDEX)
        self.assertIn("'/poster.jpg?k=' + encodeURIComponent(d.key || '')", INDEX)
        self.assertIn("d.poster === true", INDEX)

    def test_absent_art_is_memoized_without_changing_endpoint_semantics(self):
        self.assertIn("const unavailablePosterIdentities = new Set();", INDEX)
        self.assertIn("unavailablePosterIdentities.has(requestIdentity)", INDEX)
        self.assertIn("unavailablePosterIdentities.add(requestIdentity)", INDEX)
        self.assertIn("clearPosterPresentation(false)", INDEX)
        self.assertIn("i.onerror = () =>", INDEX)
        # The server still serves only an actual generated file; no placeholder
        # route is introduced that could hide a broken media-art contract.
        self.assertNotIn("path == \"/poster.jpg\"", (ROOT / "cast/marquee/api/http.py").read_text())


if __name__ == "__main__":
    unittest.main()
