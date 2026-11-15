import tempfile
import unittest
from pathlib import Path

from assmedia.instagram.page import choose_title
from assmedia.instagram.post import scan_items
from assmedia.core.tags import Tags
from tests.core.fixtures import make_post_folder


def tags(**kw):
    base = dict(title="", description="", people=[], subjects=[], themes=[],
                creator_person=None, domain=[])
    base.update(kw)
    return Tags(**base)


class FallbackTitleTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def post(self, caption, files=("X_01.jpg",)):
        make_post_folder(self.root, "X", list(files), {"username": "sideshow", "description": caption})
        return scan_items(self.root)[0][0]

    def test_untagged_title_from_caption(self):
        self.assertEqual(choose_title(self.post("Check this out!\nmore"), tags(), set()),
                         "Check this out! (sideshow)")

    def test_untagged_emoji_caption_named_by_emoji(self):
        self.assertEqual(choose_title(self.post("💣💕"), tags(), set()), "Bomb, two hearts (sideshow)")

    def test_untagged_without_words_or_emoji_names_media_kind(self):
        self.assertEqual(choose_title(self.post(":]"), tags(), set()), "Photo (sideshow)")
        self.assertEqual(choose_title(self.post("", ["X_01.jpg", "X_02.jpg"]), tags(), set()),
                         "Images (sideshow)")

    def test_untagged_name_taken_gets_shortcode(self):
        self.assertEqual(choose_title(self.post(""), tags(), {"photo (sideshow)"}), "Photo (sideshow) - X")

    def test_untagged_contact_caption_not_used(self):
        self.assertEqual(choose_title(self.post("a.b@c.com"), tags(), set()), "Photo (sideshow)")


if __name__ == "__main__":
    unittest.main()
