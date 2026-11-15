import tempfile
import unittest
from datetime import date
from pathlib import Path

from tests.x.fixtures import author, write_media, write_tweet
from assmedia.x.tweet import TweetError, html_to_text, known_tweets, load_tweet, scan_bookmarks

LONG_ID = "2120094207604035595"


class TweetTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.items, self.threads = root / "items", root / "threads"
        self.items.mkdir()


class LoadTests(TweetTestCase):
    def test_load_basic_fields(self):
        path = write_tweet(self.items, "123", ["123_01.jpg"], author=author(9, "elonmusk", "Elon Musk"),
                           content="hi", hashtags=["AI"], reply_count=4)
        t = load_tweet(path, self.items)
        self.assertEqual((t.tweet_id, t.author, t.author_name, t.author_id), ("123", "elonmusk", "Elon Musk", "9"))
        self.assertEqual(t.url, "https://x.com/elonmusk/status/123")
        self.assertEqual((t.published, t.bookmarked), (date(2026, 11, 10), date(2026, 11, 11)))
        self.assertEqual((t.text, t.hashtags, t.reply_count), ("hi", ["AI"], 4))
        self.assertEqual((t.reply_id, t.quoted_id, t.source_user, t.article_title), (None, None, None, None))
        self.assertEqual([f.name for f in t.media_files], ["123_01.jpg"])

    def test_reply_quote_and_source_fields(self):
        path = write_tweet(self.items, "124", reply_id=100, reply_to="other", conversation_id=99,
                           quoted_id=55, source_id=77, source_user=author(7, "art_muse"))
        t = load_tweet(path, self.items)
        self.assertEqual((t.reply_id, t.reply_to, t.conversation_id, t.quoted_id, t.source_user),
                         ("100", "other", "99", "55", "art_muse"))

    def test_long_ids_stay_exact(self):
        path = write_tweet(self.items, LONG_ID, quoted_id=int("2119430401701621865"))
        t = load_tweet(path, self.items)
        self.assertEqual((t.tweet_id, t.quoted_id), (LONG_ID, "2119430401701621865"))

    def test_bad_json_raises(self):
        folder = write_media(self.items, "125", [])
        (folder / "125.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(TweetError):
            load_tweet(folder / "125.json", self.items)

    def test_missing_date_raises(self):
        path = write_tweet(self.items, "126", date="")
        with self.assertRaises(TweetError):
            load_tweet(path, self.items)


class ArticleTests(TweetTestCase):
    def test_article_html_to_text(self):
        self.assertEqual(html_to_text("<p>A</p><p>B &amp; C</p>"), "A\n\nB & C")

    def test_article_line_breaks_and_headings(self):
        self.assertEqual(html_to_text("<h2>Title</h2><p>one<br>two</p>"), "Title\n\none\ntwo")

    def test_article_fields_loaded(self):
        path = write_tweet(self.items, "127", article={"id": "1", "title": "Harness, Loop, Graph",
                                                       "html": "<p>Body</p>"})
        t = load_tweet(path, self.items)
        self.assertEqual((t.article_title, t.article_text), ("Harness, Loop, Graph", "Body"))

    def test_article_without_html(self):
        t = load_tweet(write_tweet(self.items, "128", article={"id": "1", "title": "T"}), self.items)
        self.assertEqual((t.article_title, t.article_text), ("T", None))


RAW_ARTICLE = {"article_results": {"result": {
    "title": "Harness, Loop, Graph",
    "content_state": {
        "blocks": [
            {"key": "a", "type": "header-one", "text": "Why agents fail", "entityRanges": []},
            {"key": "b", "type": "unstyled", "text": "Use Vec<String> and a<b, R&D.", "entityRanges": []},
            {"key": "c", "type": "ordered-list-item", "text": "harness", "entityRanges": []},
            {"key": "d", "type": "ordered-list-item", "text": "loop", "entityRanges": []},
            {"key": "e", "type": "unordered-list-item", "text": "graph", "entityRanges": []},
            {"key": "f", "type": "blockquote", "text": "A quoted line.", "entityRanges": []},
            {"key": "g", "type": "atomic", "text": " ", "entityRanges": [{"key": 0, "offset": 0, "length": 1}]},
            {"key": "h", "type": "atomic", "text": " ", "entityRanges": [{"key": 1, "offset": 0, "length": 1}]},
            {"key": "i", "type": "code-block", "text": "print('hi')", "entityRanges": []},
            {"key": "j", "type": "atomic", "text": " ", "entityRanges": [{"key": 2, "offset": 0, "length": 1}]},
            {"key": "k", "type": "ordered-list-item", "text": "again one", "entityRanges": []},
        ],
        "entityMap": [
            {"key": "0", "value": {"type": "TWEET", "data": {"tweetId": "2119430401701621865"}}},
            {"key": "1", "value": {"type": "MARKDOWN", "data": {"markdown": "```py\nx = 1\n```"}}},
            {"key": "2", "value": {"type": "MEDIA", "data": {"caption": "A diagram", "mediaItems": []}}},
        ],
    },
}}}


class RawArticleTests(TweetTestCase):
    def test_raw_article_text_keeps_every_block(self):
        t = load_tweet(write_tweet(self.items, "150", article=RAW_ARTICLE), self.items)
        self.assertEqual(t.article_title, "Harness, Loop, Graph")
        self.assertEqual(t.article_text, "\n\n".join([
            "Why agents fail",
            "Use Vec<String> and a<b, R&D.",
            "1. harness\n2. loop",
            "- graph",
            "A quoted line.",
            "https://x.com/i/status/2119430401701621865",
            "```py\nx = 1\n```",
            "print('hi')",
            "A diagram",
            "1. again one",
        ]))

    def test_raw_article_without_content_state(self):
        """The Bookmarks feed carries only the title."""
        art = {"article_results": {"result": {"title": "Only a title"}}}
        t = load_tweet(write_tweet(self.items, "151", article=art), self.items)
        self.assertEqual((t.article_title, t.article_text), ("Only a title", None))

    def test_known_tweets_keeps_article_text_from_thread_copy(self):
        write_tweet(self.threads, "152", kind="thread", article=RAW_ARTICLE)
        write_tweet(self.items, "152", kind="quoted", article={"article_results": {"result": {"title": "T"}}})
        known = known_tweets(self.items, self.threads)
        self.assertTrue(known["152"].article_text.startswith("Why agents fail"))


class ScanTests(TweetTestCase):
    def test_scan_finds_only_bookmarks(self):
        write_tweet(self.items, "200", ["200_01.jpg"])
        write_tweet(self.items, "201", ["201_01.jpg"], kind="quoted")
        bookmarks, incomplete = scan_bookmarks(self.items)
        self.assertEqual(([t.tweet_id for t in bookmarks], incomplete), (["200"], []))

    def test_scan_incomplete(self):
        write_tweet(self.items, "300", ["300_01.jpg", "300_02.jpg.part"])
        write_tweet(self.items, "301", ["301_01.jpg", "301_03.jpg"])
        write_tweet(self.items, "302", ["302_01.jpg"], count=2)
        folder = write_media(self.items, "303", [])
        (folder / "303.json").write_text("{", encoding="utf-8")
        write_tweet(self.items, "304", [])  # text-only bookmark: complete
        bookmarks, incomplete = scan_bookmarks(self.items)
        self.assertEqual([t.tweet_id for t in bookmarks], ["304"])
        self.assertEqual(sorted(incomplete), ["300", "301", "302", "303"])

    def test_scan_order_newest_bookmarked_first(self):
        write_tweet(self.items, "400", date_bookmarked="2026-01-01 00:00:00")
        write_tweet(self.items, "401", date_bookmarked="2026-03-01 00:00:00")
        write_tweet(self.items, "402", date_bookmarked="2026-03-01 00:00:00")
        self.assertEqual([t.tweet_id for t in scan_bookmarks(self.items)[0]], ["402", "401", "400"])

    def test_known_tweets_precedence(self):
        write_tweet(self.threads, "500", kind="thread", content="thread copy")
        write_tweet(self.items, "500", content="bookmark copy")
        write_tweet(self.threads, "501", kind="thread", content="thread copy")
        write_tweet(self.items, "501", kind="quoted", content="quoted copy")
        write_tweet(self.threads, "502", kind="thread", content="only thread")
        write_media(self.items, "502", ["502_01.mp4"])
        known = known_tweets(self.items, self.threads)
        self.assertEqual((known["500"].text, known["501"].text, known["502"].text),
                         ("bookmark copy", "quoted copy", "only thread"))
        self.assertEqual([f.name for f in known["502"].media_files], ["502_01.mp4"])





if __name__ == "__main__":
    unittest.main()
