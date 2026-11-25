import contextlib
import io
import json
import subprocess
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
