import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from assmedia.core import fsread

from assmedia.x.prefill import (History, empty_entry, has_words, load_history, needles, prefill, settle_role, suggest,
                           write_starter)

from tests.x.fixtures import make_xpaths


def read_calls(run) -> list[list[Path]]:
    """The paths of each fsread.read_texts call made while `run()` runs."""
    calls, real = [], fsread.read_texts

    def recording(paths, *a, **k):
        calls.append(list(paths))
        return real(paths, *a, **k)

    with mock.patch("assmedia.core.fsread.read_texts", recording):
        run()
    return calls


def row(**over) -> dict:
    base = {"tweet_id": "1", "author": "someone", "author_name": "Some One", "text": "", "hashtags": [],
            "media": "photo", "article_title": None, "article_text": None, "source_user": None,
            "above": [], "below": [], "quoted": None}
    base.update(over)
    return base


def history(**over) -> History:
    names = {"claude code": ("Claude Code", "subjects", True), "claudecode": ("Claude Code", "subjects", True),
             "elon musk": ("Elon Musk", "people", True), "grok": ("Grok", "people", True),
             "history": ("History", "themes", True), "windows": ("Windows", "subjects", True),
             "prompt engineering": ("Prompt engineering", "themes", True),
             "ai": ("AI", "subjects", True), "turing machine": ("Turing Machine", "subjects", False),
             "kelly": ("Kelly", "people", False), "ff7": ("Final Fantasy VII", "subjects", True),
             "final fantasy vii": ("Final Fantasy VII", "subjects", True),
             "final fantasy": ("Final Fantasy", "subjects", True)}
    base = dict(creators={"LaurenChen": "Lauren Chen"}, unmapped={"brandco": 3}, names=names, hubs={"ai"},
                own=frozenset({"ownaccount"}))
    base.update(over)
    from collections import Counter
    base["unmapped"] = Counter(base["unmapped"])
    return History(**base)


class HasWordsTests(unittest.TestCase):
    def test_links_mentions_and_emoji_are_not_words(self):
        self.assertFalse(has_words(row(text="https://t.co/abc @someone 🔥")))
        self.assertFalse(has_words(row()))

    def test_any_allowed_text_counts(self):
        self.assertTrue(has_words(row(text="Look at this")))
        self.assertTrue(has_words(row(text="https://t.co/x", quoted={"author": "a", "author_name": "A",
                                                                      "text": "quoted words"})))
        self.assertTrue(has_words(row(below=["the author's next tweet"])))
        self.assertTrue(has_words(row(text="这种感觉真的是太帅了")))
        self.assertTrue(has_words(row(text=":D")))  # an emoticon still gets a title


class SettleRoleTests(unittest.TestCase):
    def test_exact_answers(self):
        h = history()
        self.assertEqual(settle_role(None, h), (None, "no such account"))
        self.assertEqual(settle_role("OwnAccount", h), (None, "your own account"))
        self.assertEqual(settle_role("laurenchen", h)[0], "Lauren Chen")

    def test_an_account_whose_earlier_pages_got_no_person(self):
        value, reason = settle_role("BrandCo", history())
        self.assertIsNone(value)
        self.assertIn("3 earlier bookmarks", reason)

    def test_a_new_account_is_left_to_claude(self):
        self.assertIsNone(settle_role("newperson", history()))


class SuggestTests(unittest.TestCase):
    def run_suggest(self, **over):
        found, squashed = needles(history())
        return suggest(row(**over), found, squashed)

    def test_names_of_two_words_and_one_word_people(self):
        got = self.run_suggest(text="Elon Musk says Grok beats Claude Code at history")
        self.assertEqual(got["people"], ["Elon Musk", "Grok"])
        self.assertEqual(got["subjects"], ["Claude Code"])
        self.assertEqual(got["themes"], [])  # one-word themes are ordinary words

    def test_a_one_word_name_counts_only_where_capitalized(self):
        found, squashed = needles(history(names={"cloud": ("Cloud", "people", True)}))
        self.assertEqual(suggest(row(text="saved to the cloud"), found, squashed)["people"], [])
        self.assertEqual(suggest(row(text="Cloud and Tifa"), found, squashed)["people"], ["Cloud"])

    def test_one_word_subjects_and_hub_names_are_never_suggested(self):
        got = self.run_suggest(text="Windows and AI news")
        self.assertEqual(got["subjects"], [])

    def test_a_name_no_bookmark_links_yet_needs_two_words(self):
        got = self.run_suggest(text="Kelly built a Turing Machine")
        self.assertEqual(got["people"], [])
        self.assertEqual(got["subjects"], ["Turing Machine"])

    def test_the_longest_name_wins_and_aliases_give_the_page_name(self):
        self.assertEqual(self.run_suggest(text="Final Fantasy VII remake")["subjects"], ["Final Fantasy VII"])
        self.assertEqual(self.run_suggest(text="Final Fantasy XVI")["subjects"], ["Final Fantasy"])

    def test_hashtags_and_mentions_match_with_spaces_removed(self):
        got = self.run_suggest(text="new release @elonmusk", hashtags=["ClaudeCode"])
        self.assertEqual(got["subjects"], ["Claude Code"])
        self.assertEqual(got["people"], ["Elon Musk"])

    def test_bios_are_never_read(self):
        got = self.run_suggest(text="hello", author_name="Some One")
        self.assertEqual(got, {"people": [], "subjects": [], "themes": []})


class PrefillTests(unittest.TestCase):
    def test_a_bookmark_with_no_words_settles_its_text_fields(self):
        rows = [row(tweet_id="9", text="https://t.co/x", author="LaurenChen")]
        starter, summary = prefill(rows, history())
        self.assertEqual(starter["9"], {**empty_entry(), "creator_person": "Lauren Chen"})
        self.assertEqual(set(rows[0]["prefill"]["settled"]),
                         {"title", "description", "people", "subjects", "themes", "domain",
                          "creator_person", "quoted_person", "source_person"})
        self.assertEqual(rows[0]["prefill"]["to_tag"], [])
        self.assertEqual((summary["no_words"], summary["nothing_to_tag"]), (1, 1))

    def test_a_bookmark_with_text_keeps_its_judgment_fields(self):
        rows = [row(tweet_id="7", text="Elon Musk on Claude Code", author="newperson",
                    quoted={"author": "BrandCo", "author_name": "Brand", "text": "launch"})]
        starter, _ = prefill(rows, history())
        p = rows[0]["prefill"]
        self.assertEqual(p["to_tag"], ["title", "description", "people", "subjects", "themes", "creator_person",
                                       "domain"])
        self.assertEqual(sorted(p["settled"]), ["quoted_person", "source_person"])
        self.assertEqual(p["suggestions"]["subjects"], ["Claude Code"])
        self.assertEqual(set(starter["7"]), set(empty_entry()))

    def test_write_starter_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags" / "b.json"
            self.assertTrue(write_starter(path, {"1": empty_entry()}))
            path.write_text("{}", encoding="utf-8")
            self.assertFalse(write_starter(path, {"1": empty_entry()}))
            self.assertEqual(path.read_text(encoding="utf-8"), "{}")


class LoadHistoryTests(unittest.TestCase):
    def test_load_history_reads_wiki_pages_in_one_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            xp = make_xpaths(Path(tmp))
            xp.core.entities.mkdir(parents=True)
            for name in ("Ann", "Bob", "Cy"):
                (xp.core.entities / f"{name}.md").write_text('---\ntype: "person"\n---\n', encoding="utf-8")
            calls = read_calls(lambda: load_history(xp))
        self.assertEqual([len(c) for c in calls], [3])

    def test_reads_pages_creators_and_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            xp = make_xpaths(Path(tmp))
            pages = xp.core.pages
            pages.mkdir(parents=True)
            (pages / "A.md").write_text('---\ntype: "source"\nsource_author: "brandco"\npeople:\n'
                                        '  - "[[Elon Musk]]"\nsubjects:\n  - "[[Claude Code]]"\n---\n',
                                        encoding="utf-8")
            (pages / "B.md").write_text('---\ntype: "source"\nsource_author: "LaurenChen"\nthemes:\n'
                                        '  - "[[Claude Code]]"\n  - "[[Claude Code]]"\n---\n', encoding="utf-8")
            xp.core.entities.mkdir(parents=True)
            (xp.core.entities / "Claude Code.md").write_text('---\ntype: "tool"\naliases:\n  - "CC CLI"\n---\n',
                                                             encoding="utf-8")
            xp.tagging.mkdir(parents=True)
            (xp.tagging / "creator-people.json").write_text(json.dumps({"LaurenChen": "Lauren Chen"}),
                                                            encoding="utf-8")
            h = load_history(xp)
        self.assertEqual(h.unmapped, {"brandco": 1})
        self.assertEqual(h.creator("laurenchen"), "Lauren Chen")
        self.assertEqual(h.names["elon musk"], ("Elon Musk", "people", True))
        self.assertEqual(h.names["claude code"][1], "themes")  # the field it's linked from most
        self.assertEqual(h.names["cc cli"][0], "Claude Code")
        self.assertEqual(h.hubs, {"ai", "coding"})


if __name__ == "__main__":
    unittest.main()
