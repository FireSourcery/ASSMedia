import tempfile
import unittest
from pathlib import Path

from tests.x.fixtures import author, write_media, write_tweet
from assmedia.x.thread import all_texts, assemble, page_media
from assmedia.x.tweet import known_tweets

ME = author(1, "artist")
OTHER = author(2, "someone_else")


class ThreadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.items, self.threads = root / "items", root / "threads"

    def known(self):
        return known_tweets(self.items, self.threads)

    def thread_tweet(self, tweet_id, **over):
        write_tweet(self.threads, tweet_id, kind="thread", **over)

    def test_bookmark_takes_article_text_from_its_lookup(self):
        """Callers pass the Bookmarks-feed copy (scan_bookmarks), which has no article text; the lookup's has."""
        from assmedia.x.tweet import scan_bookmarks
        write_tweet(self.items, "300", author=ME, article={"article_results": {"result": {"title": "Long read"}}})
        self.thread_tweet("300", author=ME, article={"article_results": {"result": {
            "title": "Long read", "content_state": {"blocks": [{"type": "unstyled", "text": "Body."}],
                                                   "entityMap": []}}}})
        (feed_copy,), _ = scan_bookmarks(self.items)
        self.assertIsNone(feed_copy.article_text)
        thread = assemble(feed_copy, self.known())
        self.assertEqual((thread.bookmark.article_title, thread.bookmark.article_text), ("Long read", "Body."))

    def test_reply_chain_above(self):
        self.thread_tweet("10", author=OTHER, content="root")
        self.thread_tweet("11", author=ME, reply_id=10, content="middle")
        self.thread_tweet("12", author=OTHER, reply_id=11, content="parent")
        write_tweet(self.items, "13", author=ME, reply_id=12, content="bookmark")
        known = self.known()
        t = assemble(known["13"], known)
        self.assertEqual([x.tweet_id for x in t.above], ["10", "11", "12"])
        self.assertTrue(t.above_complete)

    def test_own_continuation_below_ignores_others(self):
        write_tweet(self.items, "20", author=ME, content="1/3")
        self.thread_tweet("21", author=ME, reply_id=20, content="2/3")
        self.thread_tweet("22", author=OTHER, reply_id=20, content="nice")
        self.thread_tweet("23", author=ME, reply_id=21, content="3/3")
        self.thread_tweet("24", author=ME, reply_id=22, content="thanks")  # author answering someone else
        known = self.known()
        t = assemble(known["20"], known)
        self.assertEqual([x.tweet_id for x in t.below], ["21", "23"])
        self.assertEqual(t.above, [])

    def test_missing_parent_marks_incomplete(self):
        self.thread_tweet("31", author=ME, reply_id=30, content="parent of the bookmark")
        write_tweet(self.items, "32", author=ME, reply_id=31)
        known = self.known()
        t = assemble(known["32"], known)
        self.assertEqual([x.tweet_id for x in t.above], ["31"])
        self.assertFalse(t.above_complete)

    def test_missing_quoted_tweet(self):
        write_tweet(self.items, "40", quoted_id=39)
        known = self.known()
        t = assemble(known["40"], known)
        self.assertIsNone(t.quoted)
        self.assertTrue(t.quoted_missing)

    def test_quoted_tweet_found(self):
        write_tweet(self.items, "41", kind="quoted", author=OTHER, content="quoted text")
        write_tweet(self.items, "42", quoted_id=41)
        known = self.known()
        t = assemble(known["42"], known)
        self.assertEqual((t.quoted.tweet_id, t.quoted_missing), ("41", False))

    def test_page_media_order_and_author_filter(self):
        self.thread_tweet("50", author=OTHER)
        write_media(self.items, "50", ["50_01.jpg"])            # someone else's tweet above: excluded
        self.thread_tweet("51", author=ME, reply_id=50)
        write_media(self.items, "51", ["51_01.jpg"])            # the author's own tweet above: first
        write_tweet(self.items, "52", ["52_01.mp4"], author=ME, reply_id=51, quoted_id=60)
        self.thread_tweet("53", author=ME, reply_id=52)
        write_media(self.items, "53", ["53_01.png"])
        write_tweet(self.items, "60", ["60_01.jpg", "60_02.jpg"], kind="quoted", author=OTHER)
        known = self.known()
        names = [p.name for p in page_media(assemble(known["52"], known))]
        self.assertEqual(names, ["51_01.jpg", "52_01.mp4", "53_01.png", "60_01.jpg", "60_02.jpg"])

    def test_all_texts_includes_article(self):
        write_tweet(self.items, "70", kind="quoted", content="quoting nothing",
                    article={"title": "Long read", "html": "<p>article body</p>"})
        write_tweet(self.items, "71", quoted_id=70, content="look at this")
        known = self.known()
        texts = all_texts(assemble(known["71"], known))
        self.assertIn("look at this", texts)
        self.assertIn("article body", texts)
        self.assertIn("Long read", texts)

    def test_cycle_does_not_loop(self):
        self.thread_tweet("80", author=ME, reply_id=81)
        write_tweet(self.items, "81", author=ME, reply_id=80)
        known = self.known()
        t = assemble(known["81"], known)
        self.assertEqual([x.tweet_id for x in t.above], ["80"])


if __name__ == "__main__":
    unittest.main()
