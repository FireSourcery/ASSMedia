"""X's gallery-dl config: shared settings at twitter level, a bookmark block and a tweet (lookup) block.
Paths and the browser aren't in it: they're filled in from the instance config before each run."""
import json
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / "assmedia" / "x"


class OneConfigTests(unittest.TestCase):
    def setUp(self):
        self.conf = json.loads((PKG / "gallery-dl.conf").read_text(encoding="utf-8"))
        self.tw = self.conf["extractor"]["twitter"]

    def test_shared_settings(self):
        self.assertEqual(self.tw["directory"], ["{tweet_id}"])
        self.assertEqual(self.tw["filename"], "{tweet_id}_{num:>02}.{extension}")
        self.assertIs(self.tw["text-tweets"], True)
        # raw article objects (no meta, no html): html fails in the Bookmarks feed and would cost the cover
        self.assertEqual(self.tw["articles"], ["cover", "media"])

    def test_no_postprocessors_at_twitter_level(self):
        # gallery-dl adds up post-processors from every level, so these would run in both passes
        self.assertNotIn("postprocessors", self.tw)

    def test_bookmark_block(self):
        bm = self.tw["bookmark"]
        self.assertIs(bm["quoted"], True)
        self.assertIs(bm["unique"], False)
        pps = {pp["filename"]: pp for pp in bm["postprocessors"]}
        self.assertEqual(set(pps), {"{tweet_id}.json", "{tweet_id}.quoted.json"})
        self.assertEqual(pps["{tweet_id}.json"]["filter"], "not quote_id")
        self.assertEqual(pps["{tweet_id}.quoted.json"]["filter"], "quote_id")
        for pp in pps.values():
            self.assertEqual((pp["name"], pp["event"], pp["skip"]), ("metadata", "post", True))

    def test_tweet_block(self):
        tw = self.tw["tweet"]
        self.assertEqual(tw["conversations"], "accessible")  # nothing at all when the focal tweet is gone
        self.assertIs(tw["quoted"], False)
        self.assertEqual(tw["file-filter"], "author['id'] == user['id']")
        (pp,) = tw["postprocessors"]
        self.assertEqual((pp["name"], pp["event"], pp["filename"], pp["skip"]),
                         ("metadata", "post", "{tweet_id}.json", False))

    def test_output_is_the_bookmark_pass(self):
        log = self.conf["output"]["logfile"]
        self.assertEqual((log["mode"], log["level"]), ("a", "info"))


if __name__ == "__main__":
    unittest.main()
