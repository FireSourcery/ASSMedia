"""relink.py never leaves a page half-written: the new text goes to a temporary file that replaces the page."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from assmedia.core import relink

OLD, NEW = Path("D:/X"), Path("D:/ASSMedia/X")


class SafeWriteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pages = Path(self._tmp.name)

    def test_page_untouched_when_the_replace_fails(self):
        data = b'---\r\nthumbnail: "file:///D:/X/thumbs/1.jpg"\r\n---\r\n'
        page = self.pages / "A.md"
        page.write_bytes(data)
        with mock.patch("assmedia.core.relink.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                relink.relink(self.pages, OLD, NEW)
        self.assertEqual(page.read_bytes(), data)
        self.assertEqual(sorted(p.name for p in self.pages.iterdir()), ["A.md"])  # no temporary file left

    def test_replace_gives_the_new_text(self):
        page = self.pages / "A.md"
        page.write_bytes(b"![](file:///D:/X/thumbs/1.jpg)\n")
        self.assertEqual(relink.relink(self.pages, OLD, NEW), {"files": 1, "links": 1})
        self.assertEqual(page.read_bytes(), b"![](file:///D:/ASSMedia/X/thumbs/1.jpg)\n")
        self.assertEqual(sorted(p.name for p in self.pages.iterdir()), ["A.md"])


if __name__ == "__main__":
    unittest.main()
