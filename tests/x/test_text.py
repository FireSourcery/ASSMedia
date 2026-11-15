import re
import tempfile
import unittest
from pathlib import Path

from tests.x.fixtures import author, write_tweet
from assmedia.x.text import thread_sections
from assmedia.x.thread import assemble
from assmedia.x.tweet import known_tweets

ME = author(1, "some_artist", "Some Artist")
OTHER = author(2, "owl_of_atena", "Owl")


class TextTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.items, self.threads = root / "items", root / "threads"

    def render(self, tweet_id):
        known = known_tweets(self.items, self.threads)
        return "\n".join(thread_sections(assemble(known[tweet_id], known)))


class SectionTests(TextTestCase):
    def test_sections_present_and_absent(self):
        write_tweet(self.items, "10", author=ME, content="single")
        body = self.render("10")
        self.assertIn("## Bookmarked tweet", body)
        for heading in ("## Earlier in the thread", "## Continuation", "## Quoted tweet"):
            self.assertNotIn(heading, body)

        write_tweet(self.threads, "20", kind="thread", author=OTHER, content="question")
        write_tweet(self.items, "21", author=ME, reply_id=20, quoted_id=30, content="answer")
        write_tweet(self.threads, "22", kind="thread", author=ME, reply_id=21, content="more")
        write_tweet(self.items, "30", kind="quoted", author=OTHER, content="quoted")
        body = self.render("21")
        order = [body.index(h) for h in ("## Earlier in the thread", "## Bookmarked tweet", "## Continuation",
                                         "## Quoted tweet")]
        self.assertEqual(order, sorted(order))
        self.assertIn(r"**@owl\_of\_atena** (Owl) · 2026-11-10 · [on X](https://x.com/owl_of_atena/status/20)",
                      body)
        self.assertIn("> answer", body)

    def test_marks_unavailable_parts(self):
        write_tweet(self.items, "40", author=ME, reply_id=39, quoted_id=38)
        body = self.render("40")
        self.assertIn("## Earlier in the thread\n\n*(earlier tweets unavailable)*", body)
        self.assertIn("*(quoted tweet unavailable)* https://x.com/i/status/38", body)

    def test_escapes_markup(self):
        write_tweet(self.items, "50", author=ME,
                    content="[[x]] #tag <script> $x$ ==hl==\n- item\n1. one\n> q")
        body = self.render("50")
        for raw in ("[[x]]", " #tag", "$x$", "==hl=="):
            self.assertNotIn(raw, body)
        self.assertIsNone(re.search(r"(?<!\\)<script", body))
        self.assertIn(r"\<script", body)
        for line in body.splitlines():
            self.assertFalse(line.startswith("> - ") or line.startswith("> 1. ") or line.startswith("> > "), line)

    def test_empty_text(self):
        write_tweet(self.items, "60", author=ME, content="")
        self.assertIn("*(no text)*", self.render("60"))

    def test_article_section(self):
        write_tweet(self.items, "70", kind="quoted", author=OTHER, content="",
                    article={"title": "Harness, Loop, Graph", "html": "<p>Layer one.</p><p>Layer two.</p>"})
        write_tweet(self.items, "71", author=ME, quoted_id=70, content="read this")
        quoted = self.render("71").split("## Quoted tweet", 1)[1]
        self.assertIn("### Article: Harness, Loop, Graph", quoted)
        self.assertIn("> Layer one.\n>\n> Layer two.", quoted)

    def test_long_article(self):
        long_text = "word " * 4000
        write_tweet(self.items, "80", author=ME, article={"title": "Long", "html": f"<p>{long_text}</p>"})
        self.assertIn(long_text.strip(), self.render("80"))


class ContactTests(TextTestCase):
    def test_sections_keep_contact_details(self):
        """Allowed in the wiki for now (the user, 2026-11-11): the text stays word for word."""
        write_tweet(self.items, "90", kind="quoted", author=author(3, "q", "Q at q@example.com"),
                    content="+1 555 123 4567", article={"title": "Reach me", "html": "<p>x@y.io</p>"})
        write_tweet(self.items, "91", author=ME, quoted_id=90, content="mail someone@example.com")
        body = self.render("91")
        for contact in ("someone@example.com", "q@example.com", "+1 555 123 4567", "x@y.io"):
            self.assertIn(contact, body)
        self.assertNotIn("contact removed", body)


if __name__ == "__main__":
    unittest.main()
