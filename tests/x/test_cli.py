import contextlib
import io
import json
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest import mock

from assmedia.core import fsread
from assmedia.core.yamlfm import split
from tests.x.fixtures import author, make_xpaths, write_tweet
from assmedia.x.cli import cmd_build, cmd_export, cmd_pending, main

PENDING = "threads-pending.txt"
TODAY = date(2026, 11, 12)
ME = author(1, "some_artist", "Some Artist")
OTHER = author(2, "art_muse", "Art Muse")
OWN = author(3, "OwnAccount", "Me")


def json_reads(run) -> Counter:
    """How often each JSON file is read through fsread.read_texts while `run()` runs."""
    seen, real = Counter(), fsread.read_texts

    def counting(paths, *a, **k):
        seen.update(p for p in paths if p.suffix == ".json")
        return real(paths, *a, **k)

    with mock.patch("assmedia.core.fsread.read_texts", counting):
        run()
    return seen


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.xp = make_xpaths(self.root)

    def page(self, title, tweet_id):
        self.xp.core.pages.mkdir(parents=True, exist_ok=True)
        (self.xp.core.pages / f"{title}.md").write_text(f'---\ntweet_id: "{tweet_id}"\n---\n# {title}\n',
                                                        encoding="utf-8")

    def mark_run(self, *tweet_ids):
        """Lookups gallery-dl has run: -I comments their lines out in the list they were queued in (else a
        test list records them as run)."""
        pending = self.xp.crawl / PENDING
        rows = pending.read_text(encoding="utf-8").splitlines() if pending.exists() else []
        hit = set()
        for i, row in enumerate(rows):
            for tweet_id in tweet_ids:
                if row.startswith("https://") and row.endswith(f"/status/{tweet_id}"):
                    rows[i] = "# " + row
                    hit.add(tweet_id)
        if rows:
            pending.write_text("\n".join(rows) + "\n", encoding="utf-8")
        with (self.xp.crawl / "threads-test.txt").open("a", encoding="utf-8") as fp:
            for tweet_id in tweet_ids:
                if tweet_id not in hit:
                    fp.write(f"# https://x.com/someone/status/{tweet_id}\n")


class UpdateWiringTests(CliTestCase):
    def test_update_wired(self):
        with mock.patch("assmedia.x.update.cmd_update", return_value=0) as fake:
            self.assertEqual(main(["update", "--full"], xp=self.xp), 0)
        self.assertIs(fake.call_args.args[0], self.xp)
        self.assertEqual((fake.call_args.kwargs["full"], fake.call_args.kwargs["lookups"]), (True, None))


class PendingTests(CliTestCase):
    def test_pending_command_reads_each_tweet_json_once(self):
        write_tweet(self.xp.core.items, "1")
        write_tweet(self.xp.core.items, "2", reply_id=1)
        write_tweet(self.xp.threads, "5", kind="thread")
        with contextlib.redirect_stdout(io.StringIO()):
            seen = json_reads(lambda: main(["pending"], xp=self.xp))
        self.assertEqual(len(seen), 3)
        self.assertEqual(set(seen.values()), {1})

    def test_pending_counts(self):
        write_tweet(self.xp.core.items, "1")                      # no replies: ready
        write_tweet(self.xp.core.items, "2", reply_id=1)          # reply: waits for a lookup
        write_tweet(self.xp.core.items, "3")                      # already has a page
        write_tweet(self.xp.core.items, "4", ["4_01.jpg"], count=2)  # incomplete download
        self.page("Built", "3")
        counts = cmd_pending(self.xp)
        self.assertEqual(counts, {"new": 2, "ready": 1, "waiting_lookup": 1, "added_to_list": 1,
                                  "incomplete": 1})
        self.assertIn("https://x.com/someone/status/2", (self.xp.crawl / PENDING).read_text(encoding="utf-8"))

    def test_done_lookup_makes_ready(self):
        write_tweet(self.xp.core.items, "2", reply_id=1)
        write_tweet(self.xp.threads, "2", kind="thread", reply_id=1)
        self.assertEqual(cmd_pending(self.xp)["ready"], 0)
        self.mark_run("2")
        self.assertEqual(cmd_pending(self.xp)["ready"], 1)

    def test_continuation_bookmark_still_queued(self):
        """Bookmark 21 continues bookmark 20: 20's lookup wrote 21's JSON, but 21's own lookup must still run."""
        write_tweet(self.xp.core.items, "20", reply_id=10)
        write_tweet(self.xp.core.items, "21", reply_id=20)
        for tweet_id, parent in (("10", 0), ("20", 10), ("21", 20)):
            write_tweet(self.xp.threads, tweet_id, kind="thread", reply_id=parent)
        self.mark_run("20")
        counts = cmd_pending(self.xp)
        self.assertEqual((counts["ready"], counts["waiting_lookup"], counts["added_to_list"]), (1, 1, 1))
        self.assertIn("/status/21\n", (self.xp.crawl / PENDING).read_text(encoding="utf-8"))

    def test_quoted_article_gets_its_own_lookup(self):
        write_tweet(self.xp.core.items, "40", kind="quoted", article={"article_results": {"result": {
            "title": "Long read"}}})
        write_tweet(self.xp.core.items, "41", quoted_id=40)  # no replies: needs no lookup of its own
        counts = cmd_pending(self.xp)
        self.assertEqual((counts["ready"], counts["waiting_lookup"]), (0, 1))
        self.assertIn("/status/40\n", (self.xp.crawl / PENDING).read_text(encoding="utf-8"))
        self.mark_run("40")
        self.assertEqual(cmd_pending(self.xp)["ready"], 1)

    def test_bookmarked_article_without_replies_gets_a_lookup(self):
        """The Bookmarks feed carries only an article's title, so a bookmarked article needs its own lookup."""
        write_tweet(self.xp.core.items, "42", article={"article_results": {"result": {"title": "Long read"}}})
        counts = cmd_pending(self.xp)
        self.assertEqual((counts["ready"], counts["waiting_lookup"]), (0, 1))
        self.assertIn("/status/42\n", (self.xp.crawl / PENDING).read_text(encoding="utf-8"))
        self.mark_run("42")
        self.assertEqual(cmd_pending(self.xp)["ready"], 1)

    def test_pending_ignores_built_bookmarks(self):
        write_tweet(self.xp.core.items, "5", reply_count=3)
        write_tweet(self.xp.core.items, "6", reply_id=1)
        self.page("Five", "5")
        self.page("Six", "6")
        first = cmd_pending(self.xp)
        list_file = self.xp.crawl / PENDING
        before = list_file.read_text(encoding="utf-8") if list_file.exists() else ""
        second = cmd_pending(self.xp)
        self.assertEqual((first["new"], second["new"], second["added_to_list"]), (0, 0, 0))
        self.assertEqual(list_file.read_text(encoding="utf-8") if list_file.exists() else "", before)


class BuildTestCase(CliTestCase):
    def tags_file(self, entries):
        path = self.root / "tags.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return path

    def build(self, entries):
        return cmd_build(self.xp, self.tags_file(entries), TODAY)

    def pages(self):
        folder = self.xp.core.pages
        return sorted(folder.glob("*.md")) if folder.exists() else []

    def creators(self):
        path = self.xp.core.tagging / "creator-people.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class ExportTests(BuildTestCase):
    def test_export_ready_only_with_thread_and_quote(self):
        write_tweet(self.xp.threads, "10", kind="thread", author=OTHER, content="parent text")
        write_tweet(self.xp.core.items, "11", author=ME, reply_id=10, quoted_id=20, content="reply text")
        write_tweet(self.xp.threads, "11", kind="thread", author=ME, reply_id=10, content="reply text")
        write_tweet(self.xp.core.items, "20", kind="quoted", author=OTHER, content="quoted text")
        write_tweet(self.xp.core.items, "12", author=ME, reply_id=99)  # lookup not done yet
        self.mark_run("11")
        out = cmd_export(self.xp, "first", 10)
        raw = out.read_text(encoding="utf-8")
        rows = json.loads(raw)
        self.assertEqual([r["tweet_id"] for r in rows], ["11"])
        row = rows[0]
        self.assertEqual((row["author"], row["author_name"], row["text"]), ("some_artist", "Some Artist", "reply text"))
        self.assertEqual(row["above"], [{"author": "art_muse", "author_name": "Art Muse", "text": "parent text"}])
        self.assertEqual(row["quoted"]["author"], "art_muse")
        self.assertEqual(row["quoted"]["text"], "quoted text")
        self.assertEqual(row["media"], "text")
        self.assertNotIn("bio", raw)


    def test_export_runs_the_mechanical_pass_first(self):
        write_tweet(self.xp.core.items, "60", author=ME, content="https://t.co/abc")  # no words to tag
        write_tweet(self.xp.core.items, "61", author=ME, content="a real sentence")
        rows = {r["tweet_id"]: r for r in json.loads(cmd_export(self.xp, "m1", 10).read_text(encoding="utf-8"))}
        self.assertEqual(rows["60"]["prefill"]["to_tag"], ["creator_person"])
        self.assertIn("title", rows["61"]["prefill"]["to_tag"])
        starter = json.loads((self.xp.build / "tags" / "m1.json").read_text(encoding="utf-8"))
        self.assertEqual(set(starter), {"60", "61"})
        self.assertEqual(starter["60"]["source_person"], None)

    def test_export_reads_each_tweet_json_once(self):
        write_tweet(self.xp.threads, "10", kind="thread", author=OTHER, content="parent text")
        write_tweet(self.xp.core.items, "11", author=ME, reply_id=10, quoted_id=20, content="reply text")
        write_tweet(self.xp.threads, "11", kind="thread", author=ME, reply_id=10, content="reply text")
        write_tweet(self.xp.core.items, "20", kind="quoted", author=OTHER, content="quoted text")
        write_tweet(self.xp.core.items, "12", author=ME, reply_id=99)
        self.mark_run("11")
        seen = json_reads(lambda: cmd_export(self.xp, "once", 10))
        self.assertEqual(len(seen), 5)  # 2 thread files, 2 bookmarks, 1 quoted copy
        self.assertEqual(set(seen.values()), {1})

    def test_export_never_overwrites_tags(self):
        write_tweet(self.xp.core.items, "62", author=ME)
        tags = self.xp.build / "tags" / "m2.json"
        tags.parent.mkdir(parents=True, exist_ok=True)
        tags.write_text('{"62": {"title": "Mine"}}', encoding="utf-8")
        cmd_export(self.xp, "m2", 10)
        self.assertEqual(tags.read_text(encoding="utf-8"), '{"62": {"title": "Mine"}}')


class LayoutTests(BuildTestCase):
    def test_export_goes_to_build(self):
        write_tweet(self.xp.core.items, "50", author=ME)
        self.assertEqual(cmd_export(self.xp, "b1", 10), self.xp.build / "export" / "b1.json")

    def test_creator_map_goes_to_tagging(self):
        write_tweet(self.xp.core.items, "51", author=ME)
        self.build({"51": {"title": "Art", "creator_person": "Some Artist"}})
        path = self.xp.tagging / "creator-people.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"some_artist": "Some Artist"})
        self.assertFalse((self.xp.build / "creator-people.json").exists())
        self.assertEqual(self.xp.core.tagging, self.xp.tagging)


class InstanceTests(BuildTestCase):
    def test_media_links_follow_items_folder(self):
        write_tweet(self.xp.core.items, "52", ["52_01.jpg"], author=ME)
        self.build({"52": {"title": "Pic"}})
        body = self.pages()[0].read_text(encoding="utf-8")
        self.assertIn(f"![]({self.xp.core.items.as_uri()}/52/52_01.jpg)", body)

    def test_own_accounts_come_from_xpaths(self):
        self.xp = replace(self.xp, own_accounts=frozenset({"some_artist"}))
        write_tweet(self.xp.core.items, "53", author=ME)
        self.build({"53": {"title": "Art", "creator_person": "Some Artist"}})
        self.assertEqual(self.creators(), {})


class BuildTests(BuildTestCase):
    def test_build_reads_each_tweet_json_once(self):
        write_tweet(self.xp.core.items, "30", author=ME, content="a character sheet")
        tags = self.tags_file({"30": {"title": "Character sheet", "description": "A sheet.", "domain": ["AI"]}})
        seen = json_reads(lambda: cmd_build(self.xp, tags, TODAY))
        self.assertEqual(dict(seen), {self.xp.core.items / "30" / "30.json": 1})

    def test_build_creates_page_without_raw_copy(self):
        write_tweet(self.xp.core.items, "30", author=ME, content="a character sheet")
        counts, messages = self.build({"30": {"title": "Character sheet", "description": "A sheet.",
                                              "creator_person": "Some Artist", "domain": ["AI"]}})
        self.assertEqual(counts, {"created": 1, "skipped": 0, "not_ready": 0, "thumb_failed": 0}, messages)
        (page,) = self.pages()
        self.assertEqual(page.name, "Character sheet (some_artist).md")
        meta = split(page.read_text(encoding="utf-8"))[0]
        self.assertEqual((meta["tweet_id"], meta["people"], meta["domain"]), ("30", ["[[Some Artist]]"], ["[[AI]]"]))
        self.assertFalse((self.xp.core.vault / "raw" / "X").exists())
        self.assertIn("> a character sheet", page.read_text(encoding="utf-8"))
        self.assertEqual(self.creators(), {"some_artist": "Some Artist"})

    def test_build_flags_page_named_without_a_title(self):
        """The tagger writes English titles; a page the tool had to name from raw text is reported."""
        write_tweet(self.xp.core.items, "35", author=ME, content="这种感觉真的是太帅了！")
        write_tweet(self.xp.core.items, "36", author=ME, content="tagged")
        write_tweet(self.xp.core.items, "37", ["37_01.jpg"], author=ME, content="https://t.co/x")  # no words
        counts, messages = self.build({"35": {}, "36": {"title": "Tagged one"}, "37": {}})
        self.assertEqual(counts["created"], 3)
        self.assertIn("Photo (some_artist).md", [p.name for p in self.pages()])
        flagged = [m for m in messages if "no title" in m]
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].startswith("35:"))
        self.assertIn("这种感觉真的是太帅了！ (some_artist)", flagged[0])

    def test_build_skips_existing_page(self):
        write_tweet(self.xp.core.items, "31", author=ME)
        self.build({"31": {"title": "One"}})
        counts, _ = self.build({"31": {"title": "Other title"}})
        self.assertEqual((counts["created"], counts["skipped"]), (0, 1))
        self.assertEqual(len(self.pages()), 1)

    def test_build_not_ready_reported(self):
        write_tweet(self.xp.core.items, "32", author=ME, reply_id=5)
        counts, messages = self.build({"32": {"title": "Waiting"}, "33": {"title": "Missing"}})
        self.assertEqual((counts["created"], counts["not_ready"]), (0, 2))
        self.assertTrue(any(m.startswith("32:") for m in messages))
        self.assertTrue(any(m.startswith("33:") for m in messages))

    def test_build_own_account_never_creator(self):
        write_tweet(self.xp.core.items, "34", author=OWN)
        counts, messages = self.build({"34": {"title": "Mine", "creator_person": "Me Myself"}})
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["people"], [])
        self.assertEqual(self.creators(), {})
        self.assertTrue(any("own account" in m for m in messages))

    def test_build_records_three_creator_roles(self):
        write_tweet(self.xp.core.items, "40", kind="quoted", author=author(5, "quoter_src", "Q"))
        write_tweet(self.xp.core.items, "41", author=ME, quoted_id=40, source_id=9, source_user=OTHER)
        self.build({"41": {"title": "Art", "creator_person": "Some Artist", "quoted_person": "Quinn",
                           "source_person": "Art Muse"}})
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["people"], ["[[Some Artist]]", "[[Quinn]]", "[[Art Muse]]"])
        self.assertEqual(self.creators(), {"some_artist": "Some Artist", "quoter_src": "Quinn",
                                           "art_muse": "Art Muse"})

    def test_role_without_account_dropped(self):
        write_tweet(self.xp.core.items, "42", author=ME)
        _, messages = self.build({"42": {"title": "T", "quoted_person": "Nobody"}})
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["people"], [])
        self.assertTrue(any("quoted_person" in m for m in messages))

    def test_build_earlier_mapping_wins(self):
        self.xp.core.tagging.mkdir(parents=True, exist_ok=True)
        (self.xp.core.tagging / "creator-people.json").write_text(json.dumps({"some_artist": "Sam Artist"}),
                                                               encoding="utf-8")
        write_tweet(self.xp.core.items, "50", author=ME)
        _, messages = self.build({"50": {"title": "T", "creator_person": "Some Artist"}})
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["people"], ["[[Sam Artist]]"])
        self.assertTrue(any("already mapped" in m for m in messages))

    def test_build_canonicalizes_to_existing_page(self):
        entities = self.xp.core.entities
        entities.mkdir(parents=True)
        (entities / "Rust.md").write_text('---\ntype: "tool"\naliases:\n  - "rust-lang"\n---\n# Rust\n',
                                          encoding="utf-8")
        write_tweet(self.xp.core.items, "60", author=ME)
        self.build({"60": {"title": "T", "subjects": ["Rust-Lang"]}})
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["subjects"], ["[[Rust]]"])

    def test_build_rejects_unknown_domain(self):
        write_tweet(self.xp.core.items, "61", author=ME)
        counts, messages = self.build({"61": {"title": "T", "domain": ["Cooking"]}})
        self.assertEqual(counts["created"], 0)
        self.assertTrue(any("Cooking" in m for m in messages))

    def test_title_avoids_names_elsewhere_in_vault(self):
        ig_pages = self.xp.core.collections[0].pages
        ig_pages.mkdir(parents=True)
        (ig_pages / "Rust memes (some_artist).md").write_text('---\nshortcode: "S1"\n---\n', encoding="utf-8")
        write_tweet(self.xp.core.items, "90", author=ME)
        self.build({"90": {"title": "Rust memes"}})
        self.assertEqual([p.name for p in self.pages()], ["Rust memes (some_artist) - 90.md"])

    def test_build_rejects_contact_in_title_or_description(self):
        write_tweet(self.xp.core.items, "91", author=ME)
        write_tweet(self.xp.core.items, "92", author=ME)
        counts, messages = self.build({"91": {"title": "T", "description": "Mail someone@example.com for it."},
                                       "92": {"title": "Call +1 555 123 4567"}})
        self.assertEqual((counts["created"], self.pages()), (0, []))
        self.assertTrue(any(m.startswith("91:") and "contact" in m for m in messages))
        self.assertTrue(any(m.startswith("92:") and "contact" in m for m in messages))

    def test_thumb_failure_still_builds(self):
        write_tweet(self.xp.core.items, "80", ["80_01.jpg"], author=ME)
        counts, messages = self.build({"80": {"title": "Pic"}})
        self.assertEqual((counts["created"], counts["thumb_failed"]), (1, 1))
        meta = split(self.pages()[0].read_text(encoding="utf-8"))[0]
        self.assertIsNone(meta["thumbnail"])


class ConceptCommandTests(BuildTestCase):
    def two_collection_links(self):
        ig_pages = self.xp.core.collections[0].pages
        ig_pages.mkdir(parents=True)
        (ig_pages / "An Instagram save.md").write_text('---\nshortcode: "S1"\npeople:\n  - "[[Pat]]"\n---\n',
                                                     encoding="utf-8")
        self.xp.core.pages.mkdir(parents=True)
        (self.xp.core.pages / "A bookmark.md").write_text('---\ntweet_id: "9"\npeople:\n  - "[[Pat]]"\n---\n',
                                                          encoding="utf-8")

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv), xp=self.xp)
        return code, out.getvalue()

    def test_cli_concepts_plan_uses_both_collections(self):
        self.two_collection_links()
        code, _ = self.run_main("concepts-plan", "t")
        plan = json.loads((self.xp.build / "concepts" / "t.plan.json").read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual([(e["name"], e["count"]) for e in plan["new"]], [("Pat", 2)])
        self.assertEqual(sorted(s["collection"] for s in plan["new"][0]["saves"]), ["Instagram", "X"])

    def test_cli_vocab_lists_x_links(self):
        self.two_collection_links()
        code, printed = self.run_main("vocab")
        self.assertEqual((code, json.loads(printed)["linked"]), (0, {"Pat": 2}))

    def test_cli_concepts_apply(self):
        self.two_collection_links()
        self.xp.core.index_md.parent.mkdir(parents=True, exist_ok=True)
        self.xp.core.index_md.write_text("# Index\n\n## Entities\n\n## Concepts\n", encoding="utf-8")
        entries = self.root / "c.json"
        entries.write_text(json.dumps({"Pat": {"kind": "person", "sentence": "A person.", "sources": []}}),
                           encoding="utf-8")
        code, printed = self.run_main("concepts-apply", str(entries))
        self.assertEqual(code, 0)
        self.assertIn("created 1", printed)
        page = (self.xp.core.entities / "Pat.md").read_text(encoding="utf-8")
        self.assertLess(page.index("## Instagram saves"), page.index("## X bookmarks"))

    def test_cli_concepts_plan_moves_declined(self):
        self.two_collection_links()
        self.xp.tagging.mkdir(parents=True, exist_ok=True)
        (self.xp.tagging / "declined-names.json").write_text(json.dumps({"Pat": {"count": 2, "batch": "old"}}),
                                                             encoding="utf-8")
        code, printed = self.run_main("concepts-plan", "t")
        plan = json.loads((self.xp.build / "concepts" / "t.plan.json").read_text(encoding="utf-8"))
        self.assertEqual((plan["new"], [e["name"] for e in plan["declined"]]), ([], ["Pat"]))
        self.assertIn("0 new pages, 1 declined", printed)

    def test_cli_concepts_apply_records_declined(self):
        self.two_collection_links()
        self.run_main("concepts-plan", "t")
        (self.xp.build / "concepts" / "t.json").write_text("{}", encoding="utf-8")
        code, printed = self.run_main("concepts-apply", str(self.xp.build / "concepts" / "t.json"))
        saved = json.loads((self.xp.tagging / "declined-names.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, {"Pat": {"count": 2, "batch": "t"}})
        self.assertIn("declined 1", printed)

    def test_cli_seed_declined_refuses_to_overwrite(self):
        concepts = self.xp.build / "concepts"
        concepts.mkdir(parents=True)
        (concepts / "b1.plan.json").write_text(json.dumps({"new": [{"name": "Pat", "count": 2}]}), encoding="utf-8")
        (concepts / "b1.json").write_text("{}", encoding="utf-8")
        code, printed = self.run_main("seed-declined")
        path = self.xp.tagging / "declined-names.json"
        self.assertEqual((code, json.loads(path.read_text(encoding="utf-8"))), (0, {"Pat": {"count": 2, "batch": "b1"}}))
        self.assertIn("seeded 1 declined names: Pat", printed)
        path.write_text("{}", encoding="utf-8")
        code, printed = self.run_main("seed-declined")
        self.assertEqual((code, path.read_text(encoding="utf-8")), (1, "{}"))


if __name__ == "__main__":
    unittest.main()
