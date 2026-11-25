import argparse
import contextlib
import email.message
import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import film  # noqa: E402


class BuildTest(unittest.TestCase):
    def test_custom_canvas_full_contact_sheet_and_score_duration(self):
        film.load_conf()

        def ffmpeg(*args):
            return subprocess.run(
                [film.ffmpeg(), "-v", "error", *args],
                capture_output=True,
                check=True,
            ).stdout

        def make_card(scene, out):
            ffmpeg("-f", "lavfi", "-i", f"color={scene['title']}:s=128x72",
                   "-frames:v", "1", out)

        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / "film").mkdir()
            (root / "clips").mkdir()
            (root / "film/scenes.json").write_text(json.dumps({
                "size": "112x64",
                "music": "film/score.flac",
                "scenes": [
                    {"type": "card", "title": "red", "seconds": 3},
                    {"type": "clip", "name": "blue"},
                    {"type": "card", "title": "lime", "seconds": 3},
                ],
            }))
            ffmpeg("-f", "lavfi", "-i", "color=blue:s=128x72:r=24:d=24",
                   "-c:v", "libx264", str(root / "clips/blue.mp4"))
            ffmpeg("-f", "lavfi", "-i", "sine=sample_rate=44100:duration=31",
                   str(root / "film/score.flac"))
            with patch.object(film, "ROOT", work), patch.object(film, "card", make_card), \
                    contextlib.redirect_stdout(io.StringIO()):
                film.build(None)

            output = str(root / "out/film.mp4")
            frames = ffmpeg("-i", output, "-map", "0:v:0", "-f", "framehash", "-").decode().splitlines()
            self.assertIn("#dimensions 0: 112x64", frames)
            self.assertEqual(sum(not line.startswith("#") for line in frames), 30 * 24)

            packets = ffmpeg("-i", output, "-map", "0:a:0", "-c", "copy", "-f", "framecrc", "-").decode().splitlines()
            self.assertIn("#tb 0: 1/44100", packets)
            last_pts, last_duration = map(int, packets[-1].split(",")[2:4])
            self.assertEqual(last_pts + last_duration, 30 * 44100)

            sheet = str(root / "sheets/film.png")
            for x, y, channel in [(160, 91, 0), (160, 273, 2), (1760, 637, 1)]:
                pixel = ffmpeg("-i", sheet, "-vf", f"crop=1:1:{x}:{y}", "-f", "rawvideo", "-")
                self.assertEqual(len(pixel), 3)
                self.assertGreater(pixel[channel], 200)
                self.assertLess(max(pixel[:channel] + pixel[channel + 1:]), 40)


def redirected(url, newurl, code=302, method="GET"):
    """Run SafeRedirect on a request carrying the key, without any network."""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", "Bearer secret")
    return film.SafeRedirect().redirect_request(req, io.BytesIO(), code, "Found", email.message.Message(), newurl)


class RedirectTest(unittest.TestCase):
    def setUp(self):
        film.CONF.clear()

    def auth(self, req):
        return {k.lower(): v for k, v in req.header_items()}.get("authorization")

    def test_same_origin_keeps_key(self):
        new = redirected("https://gw.example/v1/videos/1/content", "/v1/files/1")
        self.assertEqual(new.full_url, "https://gw.example/v1/files/1")
        self.assertEqual(self.auth(new), "Bearer secret")

    def test_other_host_port_or_scheme_drops_key(self):
        for target in ("https://storage.example/clip.mp4", "https://gw.example:8443/clip.mp4",
                       "http://localhost/clip.mp4"):
            with self.subTest(target=target):
                new = redirected("https://gw.example/v1/videos/1/content", target)
                self.assertEqual(new.full_url, target)
                self.assertIsNone(self.auth(new))

    def test_redirect_to_plain_http_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            redirected("https://gw.example/v1/videos/1/content", "http://storage.example/clip.mp4")
        self.assertIn("FILM_ALLOW_HTTP", str(cm.exception))
        with self.assertRaises(urllib.error.HTTPError):
            redirected("https://gw.example/v1/x", "file:///etc/passwd")

    def test_opener_uses_safe_redirect(self):
        self.assertTrue(any(isinstance(h, film.SafeRedirect) for h in film.OPENER.handlers))


class UrlRuleTest(unittest.TestCase):
    def setUp(self):
        film.CONF.clear()

    def test_https_and_loopback_http_allowed(self):
        for url in ("https://gateway.example/v1", "http://localhost:8190/v1", "http://127.0.0.1/v1",
                    "http://[::1]:8000/v1"):
            with self.subTest(url=url):
                self.assertIsNone(film.url_problem(url))

    def test_plain_http_refused_unless_allowed(self):
        msg = film.url_problem("http://203.0.113.7:8190/v1")
        self.assertIn("FILM_ALLOW_HTTP=1", msg)
        film.CONF["FILM_ALLOW_HTTP"] = "1"
        self.assertIsNone(film.url_problem("http://203.0.113.7:8190/v1"))

    def test_other_schemes_refused(self):
        film.CONF["FILM_ALLOW_HTTP"] = "1"
        for url in ("file:///etc/passwd", "ftp://host/x", "gateway.example/v1", ""):
            with self.subTest(url=url):
                self.assertIsNotNone(film.url_problem(url))

    def test_need_url_exits_with_the_reason(self):
        film.CONF["FILM_VIDEO_BASE_URL"] = "http://gateway.example/v1"
        with self.assertRaises(SystemExit) as cm:
            film.need_url("FILM_VIDEO_BASE_URL")
        self.assertIn("FILM_ALLOW_HTTP", str(cm.exception.code))

    def test_fetch_refuses_before_any_network(self):
        with tempfile.TemporaryDirectory() as work, patch.object(film.OPENER, "open") as opened:
            with self.assertRaises(SystemExit):
                film.fetch("http://images.example/a.png", os.path.join(work, "a.png"))
            opened.assert_not_called()


class PathTest(unittest.TestCase):
    def test_shot_names(self):
        for good in ("approach", "tower-climb", "3-waves"):
            self.assertEqual(film.shot_name(good), good)
        for bad in ("../x", "a/b", "Tower", "-x", "", "a b", "a.mp4", None):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                film.shot_name(bad)

    def test_paths_stay_in_the_project(self):
        with tempfile.TemporaryDirectory() as work, patch.object(film, "ROOT", work):
            os.makedirs(os.path.join(work, "keyframes"))
            self.assertIsNone(film.path_problem("keyframes/a.png"))
            self.assertIsNone(film.path_problem(os.path.join(work, "keyframes/a.png")))
            self.assertEqual(film.inside("keyframes/a.png", "--ref"), os.path.join(work, "keyframes/a.png"))
            for bad in ("../a.png", "keyframes/../../a.png", "/etc/passwd", ".", ""):
                with self.subTest(bad=bad):
                    self.assertIsNotNone(film.path_problem(bad))
                    with self.assertRaises(SystemExit) as cm:
                        film.inside(bad, "--ref")
                    self.assertIn("outside the project", str(cm.exception.code))

    def test_symlink_out_of_the_project_is_refused(self):
        with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as other, \
                patch.object(film, "ROOT", work):
            os.symlink(other, os.path.join(work, "keyframes"))
            self.assertIsNotNone(film.path_problem("keyframes/a.png"))

    def test_render_refuses_a_bad_name_before_any_call(self):
        with patch.object(film, "http") as call, self.assertRaises(SystemExit):
            film.render(argparse.Namespace(name="../../x", seed=None, resume=None))
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
