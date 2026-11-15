import tempfile
import unittest
from datetime import date
from pathlib import Path

from assmedia.core.yamlfm import split
from tests.x.fixtures import author, write_media, write_tweet
from assmedia.x.page import choose_x_title, classify, media_lines, render_x_page, x_thumb_ref
from assmedia.x.tags import XTags
from assmedia.x.text import thread_sections
from assmedia.x.thread import assemble
from assmedia.x.tweet import known_tweets

LONG_ID = "2120094207604035595"
ITEMS, THUMBS = "file:///D:/m/raw/X/items", "file:///D:/m/raw/X/thumbs"
ME = author(1, "some_artist", "Some Artist")
OTHER = author(2, "other", "Other")
PROPS = ["type", "source", "tweet_id", "source_url", "source_author", "source_author_name", "published", "saved",
         "media", "files", "people", "subjects", "themes", "hashtags", "domain", "description", "online", "thumbnail",
         "created", "tags", "created_by"]


class PageTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.items, self.threads = root / "items", root / "threads"

    def thread(self, tweet_id):
        known = known_tweets(self.items, self.threads)
        return assemble(known[tweet_id], known)


class ClassifyTests(PageTestCase):
    def test_media_classification(self):
        p = Path
        self.assertEqual(classify([]), "text")
        self.assertEqual(classify([p("a_01.jpg")]), "photo")
        self.assertEqual(classify([p("a_01.jpg"), p("a_02.png")]), "carousel")
        self.assertEqual(classify([p("a_01.jpg"), p("a_02.mp4")]), "video")
        write_tweet(self.items, "60", ["60_01.jpg"], kind="quoted", author=OTHER)
        write_tweet(self.items, "61", author=ME, quoted_id=60, content="look")
        page = render_x_page(self.thread("61"), XTags(), title="T", thumb=None, created=date(2026, 11, 12), items_url=ITEMS)
        self.assertEqual(split(page)[0]["media"], "photo")


class RenderTests(PageTestCase):
    def test_page_properties_order_and_values(self):
        write_tweet(self.items, LONG_ID, [f"{LONG_ID}_01.mp4"], author=ME,
                    date_bookmarked="2026-11-11 05:50:12", hashtags=["AIart"])
        tags = XTags(title="T", description="A video.", people=["Pat"], subjects=["Rust"], themes=["Memes"],
                     domain=["AI"], creator_person="Some Artist")
        text = render_x_page(self.thread(LONG_ID), tags, title="T (some_artist)", thumb=x_thumb_ref(LONG_ID, THUMBS),
                             created=date(2026, 11, 12), items_url=ITEMS)
        meta, _ = split(text)
        self.assertEqual(list(meta), PROPS)
        self.assertIn(f'tweet_id: "{LONG_ID}"\n', text)
        self.assertEqual((meta["type"], meta["source"], meta["source_author"], meta["source_author_name"]),
                         ("source", "X", "some_artist", "Some Artist"))
        self.assertEqual(meta["hashtags"], ["AIart"])
        self.assertEqual(meta["source_url"], f"https://x.com/some_artist/status/{LONG_ID}")
        self.assertEqual((meta["published"], meta["saved"], meta["media"], meta["files"]),
                         ("2026-11-10", "2026-11-11", "video", "1"))
        self.assertEqual(meta["people"], ["[[Pat]]", "[[Some Artist]]"])
        self.assertEqual((meta["subjects"], meta["themes"], meta["domain"]), (["[[Rust]]"], ["[[Memes]]"], ["[[AI]]"]))
        self.assertEqual((meta["description"], meta["online"]), ("A video.", True))
        self.assertEqual(meta["thumbnail"], f"file:///D:/m/raw/X/thumbs/{LONG_ID}.jpg")
        self.assertEqual((meta["tags"], meta["created_by"]), (["source", "x"], "claude"))

    def test_saved_falls_back_to_published(self):
        write_tweet(self.items, "70", author=ME, date_bookmarked="")
        meta = split(render_x_page(self.thread("70"), XTags(), title="T", thumb=None, created=date(2026, 11, 12), items_url=ITEMS))[0]
        self.assertEqual(meta["saved"], "2026-11-10")
        self.assertIsNone(meta["thumbnail"])

    def test_files_counts_page_media(self):
        write_tweet(self.threads, "79", kind="thread", author=ME)
        write_media(self.items, "79", ["79_01.jpg"])
        write_tweet(self.items, "80", ["80_01.jpg", "80_02.jpg"], author=ME, reply_id=79, quoted_id=81)
        write_tweet(self.items, "81", ["81_01.mp4"], kind="quoted", author=OTHER)
        meta = split(render_x_page(self.thread("80"), XTags(), title="T", thumb=None, created=date(2026, 11, 12), items_url=ITEMS))[0]
        self.assertEqual((meta["files"], meta["media"]), ("4", "video"))

    def test_body_media_order(self):
        write_tweet(self.items, "90", ["90_01.jpg"], author=ME, quoted_id=91)
        write_tweet(self.items, "91", ["91_01.mp4"], kind="quoted", author=OTHER)
        thread = self.thread("90")
        body = split(render_x_page(thread, XTags(), title="My title", thumb=None, created=date(2026, 11, 12), items_url=ITEMS))[1]
        self.assertEqual(media_lines(thread, ITEMS), [
            "![](file:///D:/m/raw/X/items/90/90_01.jpg)",
            '<video controls preload="metadata" src="file:///D:/m/raw/X/items/91/91_01.mp4"></video>'])
        self.assertEqual(body, "\n# My title\n\n" + "\n\n".join(media_lines(thread, ITEMS)) + "\n\n"
                         + "\n".join(thread_sections(thread)).rstrip("\n") + "\n")
        self.assertIn("## Bookmarked tweet", body)
        self.assertNotIn("![[", body)

    def test_page_text_keeps_contact_details(self):
        write_tweet(self.items, "100", author=ME, content="mail me at someone@example.com")
        page = render_x_page(self.thread("100"), XTags(), title="T", thumb=None, created=date(2026, 11, 12), items_url=ITEMS)
        self.assertIn("someone@example.com", page)
        self.assertNotIn("contact removed", page)

    def test_people_includes_three_creators_deduped(self):
        write_tweet(self.items, "110", author=ME)
        tags = XTags(people=["Ana", "artist one"], creator_person="Artist One", quoted_person="Bo",
                     source_person="ana")
        meta = split(render_x_page(self.thread("110"), tags, title="T", thumb=None, created=date(2026, 11, 12), items_url=ITEMS))[0]
        self.assertEqual(meta["people"], ["[[Ana]]", "[[artist one]]", "[[Bo]]"])


class LinkTests(unittest.TestCase):
    def test_links_with_a_space_are_encoded(self):
        url = Path("D:/m/X Bookmarks/thumbs").as_uri()
        self.assertEqual(x_thumb_ref("1", url).prop, "file:///D:/m/X%20Bookmarks/thumbs/1.jpg")


class TitleTests(PageTestCase):
    def test_title_collision_suffix(self):
        write_tweet(self.items, "120", author=ME)
        thread = self.thread("120")
        first = choose_x_title(thread, XTags(title="Rust memes"), set())
        self.assertEqual(first, "Rust memes (some_artist)")
        self.assertEqual(choose_x_title(thread, XTags(title="Rust memes"), {first.lower()}),
                         "Rust memes (some_artist) - 120")

    def test_title_cjk_byte_limit(self):
        write_tweet(self.items, "130", author=author(3, "mingzi206"))
        title = choose_x_title(self.thread("130"), XTags(title="天" * 300), set())
        self.assertLessEqual(len(title), 80)
        self.assertLessEqual(len(title.encode("utf-8")), 200)
        self.assertTrue(title.endswith(" (mingzi206)"))

    def title(self, tweet_id, taken=()):
        return choose_x_title(self.thread(tweet_id), XTags(), set(taken))

    def test_empty_title_uses_tweet_text(self):
        write_tweet(self.items, "140", author=ME, content="Farron")
        self.assertEqual(self.title("140"), "Farron (some_artist)")
        self.assertEqual(self.title("140", {"farron (some_artist)"}), "Farron (some_artist) - 140")

    def test_fallback_title_cleans_text(self):
        write_tweet(self.items, "141", author=ME,
                    content="@a @b Real men manage their own memory https://t.co/x #rust\nsecond line")
        write_tweet(self.items, "142", author=ME, content="#Tifa #FF7")
        write_tweet(self.items, "143", author=ME, content="Price: $5 [new] https://t.co/y")
        self.assertEqual(self.title("141"), "Real men manage their own memory (some_artist)")
        self.assertEqual(self.title("142"), "Tifa FF7 (some_artist)")
        self.assertEqual(self.title("143"), "Price 5 new (some_artist)")

    def test_fallback_title_order(self):
        write_tweet(self.items, "144", author=ME, content="https://t.co/abc",
                    article={"article_results": {"result": {"title": "Harness, Loop, Graph"}}})
        write_tweet(self.items, "145", kind="quoted", author=OTHER, content="the quoted words")
        write_tweet(self.items, "146", author=ME, content="", quoted_id=145)
        self.assertEqual(self.title("144"), "Harness, Loop, Graph (some_artist)")
        self.assertEqual(self.title("146"), "the quoted words (some_artist)")

    def test_fallback_title_without_text_names_media(self):
        write_tweet(self.items, "147", ["147_01.mp4"], author=ME, content="")
        write_tweet(self.items, "148", ["148_01.jpg"], author=ME, content="https://t.co/x")
        write_tweet(self.items, "149", ["149_01.jpg", "149_02.jpg"], author=ME, content="")
        write_tweet(self.items, "150", author=ME, content="call +1 555 123 4567")
        write_tweet(self.items, "152", ["152_01.mp4"], author=ME, content="🌙 ✨!")
        self.assertEqual([self.title(i) for i in ("147", "148", "149", "150", "152")],
                         ["Video (some_artist)", "Photo (some_artist)", "Images (some_artist)",
                          "Tweet (some_artist)", "Video (some_artist)"])

    def test_fallback_title_cjk_first_line(self):
        write_tweet(self.items, "151", author=author(3, "ToyGame5484"), content="今日はミステリー記念日📚\nエドガー")
        self.assertEqual(self.title("151"), "今日はミステリー記念日📚 (ToyGame5484)")


if __name__ == "__main__":
    unittest.main()
