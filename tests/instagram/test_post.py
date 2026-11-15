import tempfile
import unittest
from datetime import date
from pathlib import Path

from assmedia.instagram.post import scan_items
from tests.core.fixtures import make_post_folder


class ScanItemsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def scan_one(self, files, data=None, drop=()):
        make_post_folder(self.root, "X", files, data, drop)
        return scan_items(self.root)

    def test_single_mp4_is_video(self):
        posts, _ = self.scan_one(["X_01.mp4"])
        self.assertEqual(posts[0].media, "video")
        self.assertEqual(len(posts[0].media_files), 1)

    def test_single_jpg_is_photo(self):
        posts, _ = self.scan_one(["X_01.jpg"])
        self.assertEqual(posts[0].media, "photo")

    def test_multiple_files_is_carousel(self):
        posts, _ = self.scan_one(["X_02.mp4", "X_01.jpg"])
        self.assertEqual(posts[0].media, "carousel")
        self.assertEqual([f.name for f in posts[0].media_files], ["X_01.jpg", "X_02.mp4"])

    def test_json_fields_mapped(self):
        posts, _ = self.scan_one(["X_01.jpg"], {"description": "hello"}, drop=("tags",))
        post = posts[0]
        self.assertEqual(post.shortcode, "X")
        self.assertEqual(post.published, date(2026, 11, 6))
        self.assertEqual(post.caption, "hello")
        self.assertEqual(post.hashtags, [])
        self.assertEqual(post.username, "someone")
        self.assertEqual(post.fullname, "Some One")
        self.assertEqual(post.url, "https://www.instagram.com/p/X/")

    def test_scan_reports_incomplete(self):
        posts, incomplete = self.scan_one([])
        self.assertEqual(posts, [])
        self.assertEqual(incomplete, ["X"])

    def test_partial_download_is_incomplete(self):
        posts, incomplete = self.scan_one(["X_01.mp4.part"])
        self.assertEqual(posts, [])
        self.assertEqual(incomplete, ["X"])

    def test_part_file_alongside_media_is_incomplete(self):
        _, incomplete = self.scan_one(["X_01.jpg", "X_02.jpg", "X_03.jpg.part"], {"count": 3})
        self.assertEqual(incomplete, ["X"])

    def test_numbering_gap_is_incomplete(self):
        _, incomplete = self.scan_one(["X_01.jpg", "X_03.jpg"])
        self.assertEqual(incomplete, ["X"])

    def test_fewer_files_than_count_is_incomplete(self):
        _, incomplete = self.scan_one(["X_01.jpg", "X_02.jpg"], {"count": 8})
        self.assertEqual(incomplete, ["X"])

    def test_audio_counts_one_extra_file(self):
        posts, incomplete = self.scan_one(["X_01.mp4"], {"count": 2, "audio_title": "Original audio"})
        self.assertEqual((len(posts), incomplete), (1, []))

    def test_no_audio_needs_every_file(self):
        _, incomplete = self.scan_one(["X_01.jpg"], {"count": 2})
        self.assertEqual(incomplete, ["X"])

    def test_corrupt_json_is_incomplete(self):
        folder = make_post_folder(self.root, "X", ["X_01.jpg"])
        (folder / "X.json").write_text("{", encoding="utf-8")
        self.assertEqual(scan_items(self.root), ([], ["X"]))

    def test_missing_post_date_is_incomplete(self):
        _, incomplete = self.scan_one(["X_01.jpg"], drop=("post_date",))
        self.assertEqual(incomplete, ["X"])


class MissingItemsTests(unittest.TestCase):
    def test_scan_missing_folder(self):
        """A new instance has no items\\ until its first download works: nothing is pending, nothing fails."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(scan_items(Path(tmp) / "items"), ([], []))



if __name__ == "__main__":
    unittest.main()
