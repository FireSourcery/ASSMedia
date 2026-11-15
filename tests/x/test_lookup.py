import json
import tempfile
import unittest
from pathlib import Path

from tests.x.fixtures import author, write_tweet
from assmedia.x.lookup import add_lookups, lookup_done, lookup_lines, lookup_state, needs_lookup, read_skip
from assmedia.x.tweet import load_tweet

LONG_ID = "2120094207604035595"


class LookupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.items, self.threads = self.root / "items", self.root / "threads"

    def tweet(self, tweet_id, **over):
        return load_tweet(write_tweet(self.items, tweet_id, **over), self.items)

    def test_needs_lookup_rules(self):
        self.assertFalse(needs_lookup(self.tweet("1", reply_count=0)))
        self.assertTrue(needs_lookup(self.tweet("2", reply_id=1)))
        self.assertTrue(needs_lookup(self.tweet("3", reply_count=5)))

    def test_lookup_lines_exact(self):
        t = self.tweet(LONG_ID, author=author(44196397, "elonmusk"))
        post, files, url = lookup_lines(t)
        self.assertEqual(post, f'-post-filter = "author[\'id\'] == 44196397 or tweet_id < {LONG_ID} or abort()"')
        self.assertEqual(json.loads(post.partition("=")[2].strip()),
                         f"author['id'] == 44196397 or tweet_id < {LONG_ID} or abort()")
        self.assertEqual(json.loads(files.partition("=")[2].strip()), "author['id'] == 44196397")
        self.assertTrue(files.startswith("-file-filter ="))
        self.assertEqual(url, f"https://x.com/elonmusk/status/{LONG_ID}")

    def test_lookup_lines_without_author_id(self):
        t = self.tweet("9", author={"id": 0, "name": "someone", "nick": ""})
        self.assertEqual(json.loads(lookup_lines(t)[0].partition("=")[2].strip()),
                         "author['id'] == user['id'] or tweet_id < 9 or abort()")

    def test_add_lookups_skips_present_and_commented(self):
        a, b, c = self.tweet("10", reply_count=1), self.tweet("11", reply_count=1), self.tweet("12", reply_count=1)
        list_file = self.root / "threads-pending.txt"
        list_file.write_text("".join(f"# {row}\n" for row in lookup_lines(a)) + "\n".join(lookup_lines(b)) + "\n",
                             encoding="utf-8")
        self.assertEqual(add_lookups(list_file, [a, b, c]), 1)
        rows = list_file.read_text(encoding="utf-8").splitlines()
        self.assertEqual(rows[-3:], lookup_lines(c))
        self.assertEqual(add_lookups(list_file, [a, b, c]), 0)

    def test_add_lookups_creates_file(self):
        list_file = self.root / "new" / "threads-pending.txt"
        self.assertEqual(add_lookups(list_file, [self.tweet("13", reply_count=1)]), 1)
        self.assertTrue(list_file.exists())

    def test_skip_file_marks_done(self):
        t = self.tweet("20", reply_id=5)
        skip = self.root / "threads-skip.txt"
        skip.write_text("# deleted parent\n20\n\n", encoding="utf-8")
        self.assertEqual(read_skip(skip), {"20"})
        self.assertTrue(lookup_done(t, lookup_state(self.root)))
        skip.unlink()
        self.assertFalse(lookup_done(t, lookup_state(self.root)))
        self.assertEqual(read_skip(self.root / "missing.txt"), set())

    def test_thread_json_alone_is_not_done(self):
        """Another bookmark's lookup writes this tweet's JSON too; its own lookup still has to run."""
        t = self.tweet("21", reply_id=5)
        write_tweet(self.threads, "21", kind="thread")
        self.assertFalse(lookup_done(t, lookup_state(self.root)))

    def test_run_url_in_any_list_is_done(self):
        t = self.tweet("22", reply_id=5)
        (self.root / "threads-test.txt").write_text("".join(f"# {row}\n" for row in lookup_lines(t)),
                                                   encoding="utf-8")
        self.assertTrue(lookup_done(t, lookup_state(self.root)))

    def test_unrun_url_is_not_done(self):
        t = self.tweet("23", reply_id=5)
        (self.root / "threads-pending.txt").write_text("\n".join(lookup_lines(t)) + "\n", encoding="utf-8")
        self.assertFalse(lookup_done(t, lookup_state(self.root)))

    def test_failed_url_is_not_done(self):
        t = self.tweet("24", reply_id=5)
        (self.root / "threads-pending.txt").write_text("".join(f"# {row}\n" for row in lookup_lines(t)),
                                                      encoding="utf-8")
        (self.root / "threads-failed.txt").write_text("\n".join(lookup_lines(t)) + "\n", encoding="utf-8")
        self.assertFalse(lookup_done(t, lookup_state(self.root)))

    def test_renamed_failed_list_waits_for_its_retry(self):
        """The README renames threads-failed.txt before retrying: until that retry runs, the lookups aren't done."""
        t = self.tweet("26", reply_id=5)
        (self.root / "threads-pending.txt").write_text("".join(f"# {row}\n" for row in lookup_lines(t)),
                                                      encoding="utf-8")
        (self.root / "threads-retry-1.txt").write_text("\n".join(lookup_lines(t)) + "\n", encoding="utf-8")
        self.assertFalse(lookup_done(t, lookup_state(self.root)))

    def test_retried_url_is_done(self):
        t = self.tweet("25", reply_id=5)
        (self.root / "threads-pending.txt").write_text("".join(f"# {row}\n" for row in lookup_lines(t)),
                                                      encoding="utf-8")
        (self.root / "threads-retry-1.txt").write_text("".join(f"# {row}\n" for row in lookup_lines(t)),
                                                      encoding="utf-8")
        self.assertTrue(lookup_done(t, lookup_state(self.root)))


if __name__ == "__main__":
    unittest.main()
