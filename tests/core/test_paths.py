"""core.paths: the page index, read 16 at a time, the same as one at a time."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from assmedia.core import fsread
from assmedia.core.paths import page_index
from assmedia.core.yamlfm import split
from tests.core.fixtures import write_note


def read_calls(run) -> list[list[Path]]:
    """The paths of each fsread.read_texts call made while `run()` runs."""
    calls, real = [], fsread.read_texts

    def recording(paths, *a, **k):
        calls.append(list(paths))
        return real(paths, *a, **k)

    with mock.patch("assmedia.core.fsread.read_texts", recording):
        run()
    return calls


class PageIndexTests(unittest.TestCase):
    def test_page_index_same_as_one_at_a_time(self):
        from tests.core.fixtures import write_note
        with tempfile.TemporaryDirectory() as tmp:
            pages = Path(tmp)
            write_note(pages, "One", {"shortcode": "x1"})
            write_note(pages, "One - dup", {"shortcode": "x1"})
            write_note(pages, "Two", {"shortcode": "x2"})
            expected = {}
            for md in pages.glob("*.md"):
                code = split(md.read_text(encoding="utf-8"))[0].get("shortcode")
                if code:
                    expected[str(code)] = md
            self.assertEqual(page_index(pages), expected)
            self.assertEqual([len(c) for c in read_calls(lambda: page_index(pages))], [3])

    def test_page_index_other_id_property(self):
        from tests.core.fixtures import write_note
        with tempfile.TemporaryDirectory() as tmp:
            pages = Path(tmp)
            write_note(pages, "A tweet page", {"tweet_id": "2120094207604035595"})
            write_note(pages, "An Instagram page", {"shortcode": "DfaayoJABa9"})
            self.assertEqual(list(page_index(pages, "tweet_id")), ["2120094207604035595"])
            self.assertEqual(list(page_index(pages)), ["DfaayoJABa9"])


if __name__ == "__main__":
    unittest.main()
