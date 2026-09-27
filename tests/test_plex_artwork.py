import unittest
from unittest.mock import patch

from cast.marquee.services import media


class Image:
    def __init__(self, **values): self.values = values
    def get(self, key, default=None): return self.values.get(key, default)


class PlexArtworkTests(unittest.TestCase):
    def test_clean_poster_prefers_unselected_tmdb_original(self):
        images = [
            Image(key="/library/metadata/1/thumb", provider="upload", selected="1"),
            Image(key="https://other/poster.jpg", provider="imdb", selected="0"),
            Image(key="https://image.tmdb.org/original.jpg", provider="tmdb", selected="0"),
        ]
        self.assertEqual(media.select_clean_plex_poster(images),
                         "https://image.tmdb.org/original.jpg")

    def test_no_alternative_returns_empty_for_safe_fallback(self):
        self.assertEqual(media.select_clean_plex_poster([
            Image(key="/selected", provider="upload", selected="1")]), "")

    def test_clean_backdrop_uses_same_original_image_policy(self):
        images = [
            Image(key="/library/metadata/1/art", provider="upload", selected="1"),
            Image(key="https://image.tmdb.org/clean-backdrop.jpg",
                  provider="tmdb", selected="0"),
        ]
        self.assertEqual(media.select_clean_plex_art(images),
                         "https://image.tmdb.org/clean-backdrop.jpg")

    def test_external_poster_does_not_receive_plex_token(self):
        seen = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return b"image"
        with patch.object(media, "plex_creds", return_value=("http://plex", "secret")), \
             patch.object(media.urllib.request, "urlopen",
                          side_effect=lambda url, timeout: (seen.append(url) or Response())), \
             patch.object(media, "atomic_write"), \
             patch.object(media, "OUTPUT", "/tmp", create=True):
            media.transcode_to("poster.jpg", "https://image.tmdb.org/clean.jpg", 600, 900)
        inner = seen[0].split("url=", 1)[1].split("&X-Plex-Token", 1)[0]
        self.assertNotIn("secret", inner)


if __name__ == "__main__": unittest.main()
