import unittest

from assmedia.core.escape import escape_caption, quote_block


class EscapeCaptionTests(unittest.TestCase):
    def test_hashtag_escaped(self):
        self.assertEqual(escape_caption("#Unboxing"), "\\#Unboxing")

    def test_dollar_signs_escaped(self):
        self.assertEqual(escape_caption("Was $20, now $30"), "Was \\$20, now \\$30")

    def test_backslash_first(self):
        self.assertEqual(escape_caption("a\\b_c"), "a\\\\b\\_c")

    def test_list_markers_escaped(self):
        self.assertEqual(escape_caption("- one\n2. two"), "\\- one\n2\\. two")

    def test_horizontal_rule_line_escaped(self):
        self.assertEqual(escape_caption("---"), "\\---")

    def test_link_and_highlight_chars_escaped(self):
        self.assertEqual(escape_caption("[[x]] ==y== %%z%% <b>"),
                         "\\[\\[x\\]\\] \\=\\=y\\=\\= \\%\\%z\\%\\% \\<b\\>")

    def test_ampersand_escaped(self):
        self.assertEqual(escape_caption("&copy; Tom & Jerry"), "\\&copy; Tom \\& Jerry")

    def test_emoji_untouched(self):
        self.assertEqual(escape_caption("🏴‍☠️ ok"), "🏴‍☠️ ok")


class QuoteBlockTests(unittest.TestCase):
    def test_quote_block_blank_lines(self):
        self.assertEqual(quote_block("a\n\nb"), "> a\n>\n> b")


if __name__ == "__main__":
    unittest.main()
