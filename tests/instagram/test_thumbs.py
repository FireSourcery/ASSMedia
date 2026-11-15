import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from assmedia.instagram.post import scan_items
from assmedia.core.thumbs import ThumbError, make_thumb_file
from assmedia.instagram.thumbs import make_thumb
from tests.core.fixtures import make_post_folder

def _find_ffmpeg() -> Path:
    """ffmpeg from this instance's assmedia.toml if there is one, else from PATH; a path that doesn't exist skips."""
    import shutil
    from assmedia.core.config import default_config_path, load_config
    try:
        return load_config(default_config_path()).ffmpeg
    except (FileNotFoundError, ValueError):
        found = shutil.which("ffmpeg")
        return Path(found) if found else Path("ffmpeg-not-found")


FFMPEG = _find_ffmpeg()
FFPROBE = FFMPEG.with_name("ffprobe.exe")


def width_of(path: Path) -> int:
    out = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width", "-of", "csv=p=0", str(path)],
                         check=True, capture_output=True, text=True)
    return int(out.stdout.strip())


@unittest.skipUnless(FFMPEG.exists(), "ffmpeg not installed")
class MakeThumbTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "items"
        self.out = Path(self._tmp.name) / "thumbs" / "X.jpg"

    def post_with(self, name, lavfi_args):
        folder = make_post_folder(self.root, "X", [name])
        target = folder / name
        if lavfi_args is not None:
            subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi", *lavfi_args,
                            str(target)], check=True)
        return scan_items(self.root)[0][0]

    def video(self, seconds):
        return self.post_with("X_01.mp4", ["-i", f"testsrc=duration={seconds}:size=720x1280:rate=30",
                                           "-pix_fmt", "yuv420p"])

    def test_video_thumb_width(self):
        result = make_thumb(self.video(2), self.out, FFMPEG)
        self.assertEqual(result, self.out)
        self.assertEqual(width_of(self.out), 360)

    def test_short_video_falls_back_to_first_frame(self):
        make_thumb(self.video(0.4), self.out, FFMPEG)
        self.assertGreater(self.out.stat().st_size, 0)

    def test_photo_thumb_width(self):
        post = self.post_with("X_01.jpg", ["-i", "testsrc=size=1080x1080", "-frames:v", "1"])
        make_thumb(post, self.out, FFMPEG)
        self.assertEqual(width_of(self.out), 360)

    def test_existing_thumb_untouched(self):
        post = self.video(2)
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(b"existing")
        old = time.time() - 3600
        os.utime(self.out, (old, old))
        make_thumb(post, self.out, FFMPEG)
        self.assertEqual(self.out.read_bytes(), b"existing")
        self.assertAlmostEqual(self.out.stat().st_mtime, old, delta=1)

    def test_missing_ffmpeg_raises_thumb_error(self):
        with self.assertRaises(ThumbError):
            make_thumb(self.video(2), self.out, Path(self._tmp.name) / "no-ffmpeg.exe")

    def test_make_thumb_file_image(self):
        source = Path(self._tmp.name) / "art.png"
        subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1200x800",
                        "-frames:v", "1", str(source)], check=True)
        out = Path(self._tmp.name) / "thumbs" / "2120094207604035595.jpg"
        self.assertEqual(make_thumb_file(source, out, FFMPEG, "2120094207604035595"), out)
        self.assertEqual(width_of(out), 360)

    def test_make_thumb_file_error_names_label(self):
        source = Path(self._tmp.name) / "empty.mp4"
        source.write_bytes(b"")
        with self.assertRaisesRegex(ThumbError, "^2120094207604035595: "):
            make_thumb_file(source, Path(self._tmp.name) / "t.jpg", FFMPEG, "2120094207604035595")

    def test_bad_media_raises(self):
        post = self.post_with("X_01.mp4", None)  # zero-byte file
        with self.assertRaises(ThumbError):
            make_thumb(post, self.out, FFMPEG)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
