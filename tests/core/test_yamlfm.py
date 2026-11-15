import unittest
from datetime import date

from assmedia.core.yamlfm import add_aliases, dump, split


class DumpTests(unittest.TestCase):
    def test_dump_quotes_hashtags(self):
        self.assertIn('  - "#A"', dump([("hashtags", ["#A"])]))

    def test_dump_types(self):
        lines = dump([("published", date(2026, 11, 6)), ("online", True),
                      ("saved_rank", None), ("themes", []), ("files", 2)]).splitlines()
        self.assertIn("published: 2026-11-06", lines)
        self.assertIn("online: true", lines)
        self.assertIn("saved_rank:", lines)
        self.assertIn("themes: []", lines)
        self.assertIn("files: 2", lines)

    def test_dump_frame(self):
        text = dump([("a", "b")])
        self.assertTrue(text.startswith("---\n"))
        self.assertTrue(text.endswith("\n---\n"))

    def test_dump_keeps_unicode(self):
        self.assertIn('t: "Sandra 🌸"', dump([("t", "Sandra 🌸")]))


class SplitTests(unittest.TestCase):
    def test_round_trip(self):
        props = [("type", "source"), ("published", date(2026, 11, 6)), ("online", True),
                 ("people", ["[[A]]", "[[B]]"]), ("themes", []), ("saved_rank", None),
                 ("note", 'He said "hi"\nnext')]
        meta, body = split(dump(props) + "body")
        self.assertEqual(meta, {"type": "source", "published": "2026-11-06", "online": True,
                                "people": ["[[A]]", "[[B]]"], "themes": [], "saved_rank": None,
                                "note": 'He said "hi"\nnext'})
        self.assertEqual(body, "body")

    def test_parse_obsidian_block_list(self):
        meta, _ = split('---\npeople:\n  - "[[Lauren Chen]]"\n  - Miss Fortune\n---\n')
        self.assertEqual(meta["people"], ["[[Lauren Chen]]", "Miss Fortune"])

    def test_parse_single_quoted(self):
        meta, _ = split("---\nname: 'it''s'\n---\n")
        self.assertEqual(meta["name"], "it's")

    def test_parse_flow_list(self):
        meta, _ = split('---\naliases: [a, "b c"]\n---\n')
        self.assertEqual(meta["aliases"], ["a", "b c"])

    def test_unquoted_link_value_stays_text(self):
        meta, _ = split("---\nraw: [[X]]\n---\n")
        self.assertEqual(meta["raw"], "[[X]]")

    def test_windows_newlines(self):
        meta, body = split("---\r\na: x\r\n---\r\nbody")
        self.assertEqual(meta, {"a": "x"})
        self.assertEqual(body, "body")

    def test_parse_zero_indent_list(self):
        meta, _ = split('---\npeople:\n- "[[A]]"\n- B\nnext: x\n---\n')
        self.assertEqual(meta, {"people": ["[[A]]", "B"], "next": "x"})

    def test_parse_bom(self):
        meta, body = split('﻿---\na: x\n---\nbody')
        self.assertEqual((meta, body), ({"a": "x"}, "body"))

    def test_no_frontmatter(self):
        self.assertEqual(split("hello"), ({}, "hello"))


if __name__ == "__main__":
    unittest.main()


class AddAliasesTests(unittest.TestCase):
    NOTE = ('---\ntype: "person"\naliases:\n  - "Elon"\nurl: "u"\n---\n'
            "# Body\naliases:\n  - not frontmatter\n")

    def test_add_aliases_block_list(self):
        out = add_aliases(self.NOTE, ["elonmusk"])
        self.assertEqual(split(out)[0]["aliases"], ["Elon", "elonmusk"])
        self.assertEqual(out.replace('  - "elonmusk"\n', "", 1), self.NOTE)

    def test_add_aliases_flow_list(self):
        note = '---\ntype: person\naliases: [Elon, "E M"]\nurl: u\n---\nbody\n'
        out = add_aliases(note, ["elonmusk"])
        meta = split(out)[0]
        self.assertEqual(meta["aliases"], ["Elon", "E M", "elonmusk"])
        self.assertTrue(out.startswith("---\ntype: person\n"))
        self.assertTrue(out.endswith("url: u\n---\nbody\n"))

    def test_add_aliases_empty_list(self):
        out = add_aliases("---\ntype: person\naliases: []\n---\nbody\n", ["a"])
        self.assertEqual(split(out)[0], {"type": "person", "aliases": ["a"]})
        self.assertTrue(out.endswith("---\nbody\n"))

    def test_add_aliases_missing_key(self):
        out = add_aliases("---\ntype: person\n---\nbody\n", ["a"])
        self.assertEqual(split(out)[0], {"type": "person", "aliases": ["a"]})
        self.assertTrue(out.endswith("---\nbody\n"))

    def test_add_aliases_no_duplicates_case_insensitive(self):
        self.assertEqual(add_aliases(self.NOTE, ["elon", "ELON"]), self.NOTE)

    def test_add_aliases_preserves_body(self):
        out = add_aliases(self.NOTE, ["x1"])
        self.assertTrue(out.endswith("# Body\naliases:\n  - not frontmatter\n"))

    def test_add_aliases_without_frontmatter_unchanged(self):
        self.assertEqual(add_aliases("# No properties\n", ["a"]), "# No properties\n")
