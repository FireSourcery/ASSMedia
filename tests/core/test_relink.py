"""relink.py: rewrite the file:/// links in a folder of pages after a media folder moves."""
import tempfile
import unittest
from pathlib import Path

from assmedia.core.relink import relink, relink_text

OLD, NEW = Path("D:/X"), Path("D:/ASSMedia/X")


class RelinkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pages = Path(self._tmp.name) / "pages"
        self.pages.mkdir()

    def page(self, name: str, data: bytes) -> Path:
        path = self.pages / name
        path.write_bytes(data)
        return path

    def test_relink_text_replaces_every_link_and_counts_them(self):
        text = ('thumbnail: "file:///D:/X/thumbs/1.jpg"\n'
                '<video src="file:///D:/X/items/1/1_01.mp4"></video>\n![](file:///D:/X/items/1/1_02.jpg)\n')
        out, n = relink_text(text, OLD, NEW)
        self.assertEqual(n, 3)
        self.assertNotIn("file:///D:/X/", out)
        self.assertIn('src="file:///D:/ASSMedia/X/items/1/1_01.mp4"', out)

    def test_only_the_whole_folder_matches(self):
        text = "file:///D:/Xtra/a.jpg file:///D:/X2/b.jpg file:///D:/m/raw/Instagram/items/c.jpg"
        self.assertEqual(relink_text(text, OLD, NEW), (text, 0))

    def test_new_folder_with_a_space_is_encoded(self):
        out, n = relink_text("![](file:///D:/X/thumbs/1.jpg)", OLD, Path("D:/My Media/X"))
        self.assertEqual((out, n), ("![](file:///D:/My%20Media/X/thumbs/1.jpg)", 1))

    def test_rewrites_only_pages_with_links_and_keeps_line_endings(self):
        linked = self.page("A.md", b'---\r\nthumbnail: "file:///D:/X/thumbs/1.jpg"\r\n---\r\nhi \xc3\xa9\r\n')
        other = self.page("B.md", b"no links here\n")
        before = other.stat().st_mtime_ns
        self.assertEqual(relink(self.pages, OLD, NEW), {"files": 1, "links": 1})
        self.assertEqual(linked.read_bytes(),
                         b'---\r\nthumbnail: "file:///D:/ASSMedia/X/thumbs/1.jpg"\r\n---\r\nhi \xc3\xa9\r\n')
        self.assertEqual(other.stat().st_mtime_ns, before)

    def test_dry_run_writes_nothing(self):
        data = b"![](file:///D:/X/items/1/1_01.jpg)\n"
        path = self.page("A.md", data)
        self.assertEqual(relink(self.pages, OLD, NEW, dry_run=True), {"files": 1, "links": 1})
        self.assertEqual(path.read_bytes(), data)

    def test_pages_in_subfolders_too(self):
        sub = self.pages / "sub"
        sub.mkdir()
        (sub / "C.md").write_bytes(b"![](file:///D:/X/thumbs/2.jpg)")
        self.assertEqual(relink(self.pages, OLD, NEW), {"files": 1, "links": 1})


if __name__ == "__main__":
    unittest.main()
