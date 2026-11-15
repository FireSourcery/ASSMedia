import unittest

from assmedia.core.title import emoji_title, title_line




class TitleLineTests(unittest.TestCase):
    def test_drops_links_leading_mentions_and_hashtags(self):
        self.assertEqual(title_line("@a.b @c Look at this https://t.co/xyz #tag").split(), ["Look", "at", "this"])

    def test_hashtag_only_line_keeps_words(self):
        self.assertEqual(title_line("#flips #reels #utah").split(), ["flips", "reels", "utah"])

    def test_dollar_dropped(self):
        self.assertNotIn("$", title_line("Was $20"))

    def test_contact_line_skipped(self):
        self.assertEqual(title_line("Email me at a.b@c.com\nNice set").strip(), "Nice set")

    def test_emoji_dropped_from_words(self):
        self.assertEqual(title_line("Love this idea 👏").strip(), "Love this idea")

    def test_other_symbols_dropped_like_emoji(self):
        self.assertEqual(title_line("link in highlights ♡ ★").split(), ["link", "in", "highlights"])

    def test_emoji_only_line_skipped_for_later_words(self):
        self.assertEqual(title_line("💜\n.\nSecond line").strip(), "Second line")

    def test_no_words(self):
        self.assertEqual(title_line("😂😂 :]"), "")


class EmojiTitleTests(unittest.TestCase):
    def test_names_in_order_each_once(self):
        self.assertEqual(emoji_title("🌸💞🌸"), "Cherry blossom, revolving hearts")

    def test_names_come_from_cldr(self):
        self.assertEqual(emoji_title("❤️ 🤩"), "Red heart, star-struck")

    def test_skin_tones_and_variation_selectors_ignored(self):
        self.assertEqual(emoji_title("👍🏽☺️"), "Thumbs up, smiling face")

    def test_flag_gets_flag_word(self):
        self.assertEqual(emoji_title("🙏🇵🇸"), "Folded hands, Palestinian Territories flag")

    def test_no_emoji(self):
        self.assertEqual(emoji_title(":]"), "")


if __name__ == "__main__":
    unittest.main()
