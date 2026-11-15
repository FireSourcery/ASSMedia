import tempfile
import unittest
from datetime import date
from pathlib import Path

from assmedia.instagram.page import choose_title, has_contact, legacy_body_lines, render_page, safe_title, thumb_ref
from assmedia.instagram.post import scan_items
from assmedia.core.tags import Tags
from assmedia.core.yamlfm import split
from tests.core.fixtures import make_post_folder

ITEMS = "file:///D:/m/raw/Instagram/items"
THUMBS = "file:///D:/m/raw/Instagram/thumbs"


def tags(**kw):
    base = dict(title="", description="", people=[], subjects=[], themes=[],
                creator_person=None, domain=[])
    base.update(kw)
    return Tags(**base)


class TitleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        make_post_folder(Path(self._tmp.name), "DfaayoJABa9", ["DfaayoJABa9_01.mp4"],
                         {"username": "sideshow"})
        self.post = scan_items(Path(self._tmp.name))[0][0]

    def test_title_strips_illegal_chars(self):
        self.assertEqual(safe_title('Sandra 🌸 | Art: "new" #1'), "Sandra 🌸 Art new 1")

    def test_title_length(self):
        title = safe_title("word " * 40)
        self.assertLessEqual(len(title), 80)
        self.assertFalse(title.endswith(" "))

    def test_title_no_leading_or_trailing_dot(self):
        self.assertEqual(safe_title("...hidden thing."), "hidden thing")

    def test_title_collision_adds_shortcode(self):
        title = choose_title(self.post, tags(title="Miss Fortune statue unboxing"),
                             {"miss fortune statue unboxing (sideshow)"})
        self.assertEqual(title, "Miss Fortune statue unboxing (sideshow) - DfaayoJABa9")

    def test_title_keeps_creator_when_long(self):
        title = choose_title(self.post, tags(title="word " * 40), set())
        self.assertTrue(title.endswith(" (sideshow)"))
        self.assertLessEqual(len(title), 80)

    def test_title_byte_limit(self):
        title = choose_title(self.post, tags(title="測試" * 60), {"x"})
        self.assertTrue(title.endswith(" (sideshow)"))
        self.assertLessEqual(len(f"{title} - DfaayoJABa9.md".encode("utf-8")), 220)

    def test_title_fallback_when_empty(self):
        self.assertEqual(choose_title(self.post, tags(), set()), "a caption (sideshow)")


class RenderPageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def render(self, files, t, thumb=None, caption="a caption", items_url=ITEMS):
        make_post_folder(self.root, "X", files, {"description": caption})
        post = scan_items(self.root)[0][0]
        return render_page(post, t, title="Some title", saved=date(2026, 11, 10),
                           thumb=thumb, created=date(2026, 11, 11), items_url=items_url)

    def test_page_people_includes_creator_once(self):
        meta, _ = split(self.render(["X_01.mp4"], tags(people=["Lauren Chen"],
                                                       creator_person="Lauren Chen")))
        self.assertEqual(meta["people"], ["[[Lauren Chen]]"])

    def test_page_creator_added_to_people(self):
        meta, _ = split(self.render(["X_01.mp4"], tags(people=["A"], creator_person="B")))
        self.assertEqual(meta["people"], ["[[A]]", "[[B]]"])

    PLAYER2 = '<video controls preload="metadata" src="file:///D:/m/raw/Instagram/items/X/X_02.mp4"></video>'

    def test_page_body_is_media_then_caption(self):
        _, body = split(self.render(["X_01.jpg", "X_02.mp4"], tags(), thumb=thumb_ref("X", "external", THUMBS)))
        self.assertEqual(body, "\n# Some title\n\n![](file:///D:/m/raw/Instagram/items/X/X_01.jpg)\n\n"
                               + self.PLAYER2 + "\n\n> a caption\n")

    def test_page_body_has_no_links_or_thumbnail(self):
        _, body = split(self.render(["X_01.jpg", "X_02.mp4"], tags(), thumb=thumb_ref("X", "external", THUMBS)))
        self.assertNotIn("[Open ", body)
        self.assertNotIn("View on Instagram", body)
        self.assertNotIn("/thumbs/", body)

    def test_page_has_no_saved_rank(self):
        """saved_rank was the first run's crawl position; pages no longer carry it (2026-11-14)."""
        text = self.render(["X_01.mp4"], tags())
        self.assertNotIn("saved_rank", text)

    def test_page_has_no_raw_copy_link(self):
        text = self.render(["X_01.mp4"], tags())
        self.assertNotIn("[[X]]", text)
        self.assertNotIn("raw", split(text)[0])

    def test_page_ends_with_caption_quote(self):
        self.assertTrue(self.render(["X_01.mp4"], tags()).endswith("\n> a caption\n"))

    def test_page_caption_escaped(self):
        _, body = split(self.render(["X_01.mp4"], tags(), caption="Was $20\n\n#sale"))
        self.assertTrue(body.endswith("\n> Was \\$20\n>\n> \\#sale\n"))

    def test_page_caption_carriage_returns_are_line_breaks(self):
        _, body = split(self.render(["X_01.mp4"], tags(), caption="one\r\ntwo\rthree"))
        self.assertTrue(body.endswith("\n> one\n> two\n> three\n"))
        self.assertNotIn("\r", body)

    def test_page_empty_caption(self):
        self.assertTrue(self.render(["X_01.mp4"], tags(), caption="  ").endswith("\n*(no caption)*\n"))

    def test_page_properties(self):
        meta, body = split(self.render(["X_01.jpg", "X_02.mp4"],
                                       tags(description="D", subjects=["S"]),
                                       thumb=thumb_ref("X", "external", THUMBS)))
        self.assertEqual(list(meta), [
            "type", "source", "shortcode", "source_url", "source_author", "source_author_name",
            "published", "saved", "media", "files", "people", "subjects", "themes",
            "hashtags", "domain", "description", "online", "thumbnail", "created", "tags", "created_by"])
        self.assertEqual(meta["media"], "carousel")
        self.assertEqual(meta["files"], "2")
        self.assertEqual(meta["subjects"], ["[[S]]"])
        self.assertEqual(meta["online"], True)
        self.assertEqual(meta["thumbnail"], "file:///D:/m/raw/Instagram/thumbs/X.jpg")
        self.assertEqual(meta["source_author_name"], "Some One")
        self.assertTrue(body.lstrip().startswith("# Some title\n"))

    def test_page_hashtags_without_hash(self):
        make_post_folder(self.root, "X", ["X_01.mp4"], {"tags": ["#Unboxing", "#tag"]})
        post = scan_items(self.root)[0][0]
        meta, _ = split(render_page(post, tags(), title="T", saved=date(2026, 11, 10),
                                    thumb=None, created=date(2026, 11, 11), items_url=ITEMS))
        self.assertEqual(meta["hashtags"], ["Unboxing", "tag"])

    def test_photo_page_shows_photo_not_player(self):
        _, body = split(self.render(["X_01.jpg"], tags()))
        self.assertNotIn("<video", body)
        self.assertIn("![](file:///D:/m/raw/Instagram/items/X/X_01.jpg)", body)

    def test_page_domain_links(self):
        meta, _ = split(self.render(["X_01.mp4"], tags(domain=["Coding"])))
        self.assertEqual(meta["domain"], ["[[Coding]]"])

    def test_contact_caption_shown_as_written(self):
        text = self.render(["X_01.mp4"], tags(), caption="Business: a.b@c.com")
        self.assertTrue(text.endswith("\n> Business: a.b@c.com\n"))
        self.assertNotIn("Caption:", text)

    def test_has_contact_forms(self):
        self.assertTrue(has_contact("mail a.b@c.com now"))
        self.assertTrue(has_contact("call +1 (555) 123-4567"))
        self.assertFalse(has_contact("Was $20, now $30"))
        self.assertFalse(has_contact("2026-11-06 20:02"))

    def test_render_uses_given_urls(self):
        _, body = split(self.render(["X_01.jpg", "X_02.mp4"], tags(), items_url="file:///Z:/Else/items"))
        self.assertIn("![](file:///Z:/Else/items/X/X_01.jpg)", body)
        self.assertIn('src="file:///Z:/Else/items/X/X_02.mp4"', body)
        self.assertNotIn("D:/m/raw/Instagram", body)  # the fixtures' default

    def test_thumb_ref_uses_given_url(self):
        ref = thumb_ref("ab", "external", "file:///Z:/T")
        self.assertEqual(ref.prop, "file:///Z:/T/ab.jpg")
        self.assertEqual(ref.embed, "![](file:///Z:/T/ab.jpg)")

    def test_legacy_lines_use_given_urls(self):
        make_post_folder(self.root, "X", ["X_01.jpg", "X_02.mp4"])
        post = scan_items(self.root)[0][0]
        lines = legacy_body_lines(post, "file:///Z:/I", "file:///Z:/T")
        self.assertIn("![](file:///Z:/T/X.jpg)", lines)
        self.assertIn("- [Open photo 1](file:///Z:/I/X/X_01.jpg)", lines)
        self.assertIn('<video controls preload="metadata" src="file:///Z:/I/X/X_02.mp4"></video>', lines)

    def test_thumb_ref_vault(self):
        ref = thumb_ref("X", "vault", THUMBS)
        self.assertEqual(ref.prop, "[[raw/Instagram/_thumbs/X.jpg]]")
        self.assertEqual(ref.embed, "![[raw/Instagram/_thumbs/X.jpg|360]]")


if __name__ == "__main__":
    unittest.main()
