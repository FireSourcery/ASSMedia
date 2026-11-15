"""assmedia.x.scan: one listing of the downloads and one read of each tweet JSON per command."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from assmedia.core import fsread
from tests.x.fixtures import write_media, write_tweet
from assmedia.x.scan import Scan, scan


class ScanTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.items, self.threads = root / "items", root / "threads"
        self.items.mkdir()


class ScanTests(ScanTestCase):
    def test_each_json_read_once_and_each_folder_listed_once(self):
        write_tweet(self.items, "1", ["1_01.jpg"])
        write_tweet(self.items, "2", kind="quoted")
        write_tweet(self.threads, "1", kind="thread")
        write_media(self.items, "3", ["3_01.jpg"])  # a thread tweet's media, no JSON
        reads, lists = Counter(), Counter()
        real_read, real_list = fsread.read_texts, fsread.list_files

        def counting_read(paths, *a, **k):
            reads.update(paths)
            return real_read(paths, *a, **k)

        def counting_list(folders, *a, **k):
            lists.update(folders)
            return real_list(folders, *a, **k)

        with mock.patch("assmedia.core.fsread.read_texts", counting_read), \
                mock.patch("assmedia.core.fsread.list_files", counting_list):
            s = scan(self.items, self.threads)
        self.assertEqual(set(reads.values()), {1})
        self.assertEqual(len(reads), 3)
        self.assertEqual(dict(lists), {self.items / i: 1 for i in ("1", "2", "3")})
        self.assertEqual([t.tweet_id for t in s.bookmarks], ["1"])

    def test_unreadable_bookmark_json_is_incomplete(self):
        write_tweet(self.items, "4", ["4_01.jpg"])
        path = write_tweet(self.items, "5", ["5_01.jpg"])
        path.write_bytes(b"\xff\xfe{")
        s = scan(self.items, self.threads)
        self.assertEqual(([t.tweet_id for t in s.bookmarks], s.incomplete), (["4"], ["5"]))
        self.assertNotIn("5", s.known)

    def test_unreadable_quoted_copy_is_skipped(self):
        path = write_tweet(self.items, "6", kind="quoted")
        path.write_bytes(b"\xff")
        s = scan(self.items, self.threads)
        self.assertEqual((s.bookmarks, s.incomplete, s.known), ([], [], {}))

    def test_thread_tweet_media_from_items_folder(self):
        write_tweet(self.threads, "7", kind="thread")
        write_media(self.items, "7", ["7_01.jpg"])
        self.assertEqual(scan(self.items, self.threads).known["7"].media_files, [self.items / "7" / "7_01.jpg"])

    def test_media_names_from_listing(self):
        write_tweet(self.items, "8", ["8_02.mp4", "8_01.JPG", "8_1.jpg", "other.jpg"], count=2)
        self.assertEqual(scan(self.items, None).known["8"].media_files,
                         [self.items / "8" / "8_01.JPG", self.items / "8" / "8_02.mp4"])

    def test_missing_folders_give_empty_scan(self):
        gone = self.items.parent / "nope"
        self.assertEqual(scan(gone, gone), Scan([], [], {}))
        self.assertEqual(scan(self.items, None), Scan([], [], {}))

    def test_feed_copy_kept_apart_from_merged_known(self):
        write_tweet(self.items, "300", article={"article_results": {"result": {"title": "Long read"}}})
        write_tweet(self.threads, "300", kind="thread", article={"article_results": {"result": {
            "title": "Long read", "content_state": {"blocks": [{"type": "unstyled", "text": "Body."}],
                                                   "entityMap": []}}}})
        s = scan(self.items, self.threads)
        self.assertIsNone(s.bookmarks[0].article_text)
        self.assertEqual(s.known["300"].article_text, "Body.")


if __name__ == "__main__":
    unittest.main()
