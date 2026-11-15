import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from assmedia.core import fsread
from assmedia.core.concepts import (EMBED_HEADING, add_index_lines, cmd_concepts_apply, cmd_concepts_plan,
                             cmd_vocab, collect_links, concept_index, embed_block, ensure_embed,
                             link_target, render_concept, render_entity, vault_notes)
from assmedia.core.yamlfm import split
from tests.core.fixtures import make_paths, make_post_folder, write_note

INDEX = ("# Wiki index\n\n## Sources\n- [[Instagram Saves.base|Instagram saves]] — x\n\n"
         "## Entities\n*None yet. People, organizations, tools, products and channels from the sources.*\n\n"
         "## Concepts\n*None yet.*\n\n## Synthesis\n*None yet.*\n")


def read_calls(run) -> list[list[Path]]:
    """The paths of each fsread.read_texts call made while `run()` runs."""
    calls, real = [], fsread.read_texts

    def recording(paths, *a, **k):
        calls.append(list(paths))
        return real(paths, *a, **k)

    with mock.patch("assmedia.core.fsread.read_texts", recording):
        run()
    return calls


class ConceptTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        vault = root / "vault"
        self.p = make_paths(root, ffmpeg=root / "none.exe")
        self.p.domains.mkdir(parents=True)
        for hub in ("AI", "Coding"):
            (self.p.domains / f"{hub}.md").write_text("", encoding="utf-8")
        self.p.index_md.write_text(INDEX, encoding="utf-8")

    def save(self, title, sc, people=(), subjects=(), themes=(), domain=(), description="d",
             caption="cap"):
        make_post_folder(self.p.items, sc, [f"{sc}_01.mp4"], {"description": caption})
        return write_note(self.p.pages, title, {
            "shortcode": sc, "people": [f"[[{n}]]" for n in people],
            "subjects": [f"[[{n}]]" for n in subjects], "themes": [f"[[{n}]]" for n in themes],
            "domain": [f"[[{d}]]" for d in domain], "description": description})

    def apply(self, entries):
        path = Path(self._tmp.name) / "concepts.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return cmd_concepts_apply(self.p, path, date(2026, 11, 11))

    def plan(self):
        return json.loads(cmd_concepts_plan(self.p, "t").read_text(encoding="utf-8"))

    def files(self, folder):
        return sorted(f.name for f in folder.iterdir()) if folder.exists() else []


class LinkTests(ConceptTestCase):
    def test_concept_index_reads_its_pages_in_one_call(self):
        for name in ("A", "B", "C"):
            write_note(self.p.entities, name, {"type": "person", "aliases": [f"{name} alias"]})
        self.assertEqual([len(c) for c in read_calls(lambda: concept_index([self.p.entities]))], [3])

    def test_vocab_and_collect_links_read_in_bulk(self):
        for name in ("A", "B"):
            write_note(self.p.entities, name, {"type": "person"})
        for i in range(3):
            self.save(f"Save {i}", f"s{i}", people=["Ann"])
        self.assertEqual([len(c) for c in read_calls(lambda: collect_links(self.p.pages))], [3])
        self.assertEqual([len(c) for c in read_calls(lambda: cmd_vocab(self.p))], [2, 3])  # wiki, then saves

    def test_link_target_forms(self):
        self.assertEqual(link_target("[[A|b]]"), "A")
        self.assertEqual(link_target("[[A]]"), "A")
        self.assertIsNone(link_target("plain"))

    def test_collect_links_counts(self):
        self.save("One", "S1", people=["Miss Fortune"])
        self.save("Two", "S2", subjects=["miss fortune"])
        self.assertEqual(len(collect_links(self.p.pages)["Miss Fortune"]), 2)

    def test_collect_links_reads_hand_edit(self):
        self.p.pages.mkdir(parents=True)
        (self.p.pages / "Edited.md").write_text(
            '---\nshortcode: "S1"\npeople:\n  - "[[X]]"\nsubjects: []\n---\nbody\n', encoding="utf-8")
        self.assertIn("X", collect_links(self.p.pages))

    def test_concept_index_aliases(self):
        write_note(self.p.entities, "Lauren Chen", {"aliases": ["thelaurenchen"]})
        write_note(self.p.concepts, "Collectibles", {})
        index = concept_index([self.p.entities, self.p.concepts])
        self.assertEqual(index["thelaurenchen"], "Lauren Chen")
        self.assertEqual(index["lauren chen"], "Lauren Chen")
        self.assertEqual(index["collectibles"], "Collectibles")


class RenderTests(unittest.TestCase):
    def test_ensure_embed_idempotent(self):
        once = ensure_embed("# Page\n")
        self.assertEqual(ensure_embed(once), once)
        self.assertIn(EMBED_HEADING, once)

    def test_embed_block_filters(self):
        block = embed_block()
        self.assertIn('file.inFolder("wiki/sources/Instagram")', block)
        self.assertIn("file.hasLink(this.file)", block)
        self.assertIn("image: note.thumbnail", block)

    def test_render_concept_sections(self):
        text = render_concept("Collectibles", "Collectable figures and statues.", ["Collecting"],
                              ["Statue unboxing (sideshow)"], ["Coding"], date(2026, 11, 11))
        meta, body = split(text)
        self.assertEqual(list(meta), ["type", "created", "aliases", "domain", "sources", "tags",
                                      "created_by"])
        self.assertEqual(meta["type"], "concept")
        self.assertEqual(meta["domain"], ["[[Coding]]"])
        self.assertEqual(meta["sources"], ["[[Statue unboxing (sideshow)]]"])
        self.assertIn("> [!note] In one sentence\n> Collectable figures and statues.", body)
        order = [body.index(h) for h in ("# Collectibles", "## Explanation", EMBED_HEADING,
                                         "## Connections", "## My take", "## Sources")]
        self.assertEqual(order, sorted(order))

    def test_render_entity_sections(self):
        text = render_entity("Sideshow", "organization", "A collectibles company.", [], ["One"], [],
                             None, date(2026, 11, 11))
        meta, body = split(text)
        self.assertEqual(list(meta), ["type", "created", "aliases", "domain", "url", "sources",
                                      "tags", "created_by"])
        self.assertEqual((meta["type"], meta["url"], meta["tags"]), ("organization", None, ["entity"]))
        self.assertNotIn("## Clippings", body)
        order = [body.index(h) for h in ("# Sideshow", "> [!note] In one sentence", "## Overview",
                                         EMBED_HEADING, "## Connections", "## My take", "## Sources")]
        self.assertEqual(order, sorted(order))
        self.assertIn("- Concepts:\n- Related entities:", body)


class PlanTests(ConceptTestCase):
    def test_plan_captions_in_one_call_and_missing_json_is_empty(self):
        self.save("Save A", "sa", people=["Ann"], caption="first")
        self.save("Save B", "sb", people=["Ann"], caption="second")
        (self.p.items / "sb" / "sb.json").unlink()
        calls = read_calls(lambda: cmd_concepts_plan(self.p, "t"))
        plan = json.loads((self.p.build / "concepts" / "t.plan.json").read_text(encoding="utf-8"))
        (ann,) = plan["new"]
        self.assertEqual({s["page"]: s["caption"] for s in ann["saves"]}, {"Save A": "first", "Save B": ""})
        self.assertEqual([len(c) for c in calls if any(p.suffix == ".json" for p in c)], [2])

    def test_plan_threshold(self):
        self.save("One", "S1", people=["Twice"], themes=["Once"])
        self.save("Two", "S2", people=["Twice"])
        plan = self.plan()
        self.assertEqual([e["name"] for e in plan["new"]], ["Twice"])
        self.assertEqual(sorted(s["caption"] for s in plan["new"][0]["saves"]), ["cap", "cap"])

    def test_plan_fields_and_suggested_kind(self):
        self.save("One", "S1", people=["Pat"], subjects=["Thing"], themes=["Idea"])
        self.save("Two", "S2", people=["Pat"], subjects=["Thing"], themes=["Idea"])
        kinds = {e["name"]: (e["fields"], e["suggested_kind"]) for e in self.plan()["new"]}
        self.assertEqual(kinds["Pat"], (["people"], "person"))
        self.assertEqual(kinds["Idea"], (["themes"], "concept"))
        self.assertEqual(kinds["Thing"], (["subjects"], None))

    def test_plan_lists_existing_page_needing_embed(self):
        self.save("One", "S1", people=["Known"])
        page = write_note(self.p.entities, "Known", {"type": "person"}, "# Known\n")
        plan = self.plan()
        self.assertEqual(plan["needs_embed"], [str(page)])
        self.assertEqual(plan["new"], [])


class DataSplitTests(ConceptTestCase):
    def test_plan_goes_to_build(self):
        self.save("A", "a1", people=["Lauren Chen"])
        self.save("B", "b1", people=["Lauren Chen"])
        out = cmd_concepts_plan(self.p, "n")
        self.assertEqual(out, self.p.build / "concepts" / "n.plan.json")
        self.assertTrue(out.is_file())

    def test_vocab_reads_tagging_creators(self):
        self.p.tagging.mkdir(parents=True)
        (self.p.tagging / "creator-people.json").write_text('{"laurenc": "Lauren Chen"}', encoding="utf-8")
        self.assertEqual(cmd_vocab(self.p)["creators"], {"laurenc": "Lauren Chen"})


class ApplyTests(ConceptTestCase):
    def two_saves(self, name="P", field="people", **kw):
        self.save("One", "S1", **{field: [name]}, **kw)
        self.save("Two", "S2", **{field: [name]}, **kw)

    def test_apply_rejects_unlinked_source(self):
        self.two_saves()
        self.save("Three", "S3")
        with self.assertRaises(ValueError):
            self.apply({"P": {"kind": "person", "sentence": "s", "sources": ["Three"]}})
        self.assertEqual(self.files(self.p.entities), [])

    def test_apply_rejects_below_threshold(self):
        self.save("One", "S1", people=["Solo"])
        with self.assertRaises(ValueError):
            self.apply({"Solo": {"kind": "person", "sentence": "s", "sources": ["One"]}})

    def test_apply_rejects_bad_kind(self):
        self.two_saves()
        with self.assertRaisesRegex(ValueError, "thing"):
            self.apply({"P": {"kind": "thing", "sentence": "s", "sources": []}})
        self.assertEqual(self.files(self.p.entities) + self.files(self.p.concepts), [])

    def test_apply_rejects_unknown_domain(self):
        self.two_saves()
        with self.assertRaisesRegex(ValueError, "Cooking"):
            self.apply({"P": {"kind": "person", "sentence": "s", "sources": [], "domain": ["Cooking"]}})

    def test_apply_creates_concept(self):
        self.two_saves(field="themes")
        counts = self.apply({"P": {"kind": "concept", "sentence": "s", "sources": ["One"]}})
        self.assertEqual(counts["created"], 1)
        meta, _ = split((self.p.concepts / "P.md").read_text(encoding="utf-8"))
        self.assertEqual((meta["type"], meta["sources"]), ("concept", ["[[One]]"]))

    def test_apply_entity_goes_to_entities(self):
        self.two_saves(field="subjects")
        self.apply({"P": {"kind": "organization", "sentence": "s", "sources": []}})
        self.assertEqual(self.files(self.p.entities), ["P.md"])
        self.assertEqual(self.files(self.p.concepts), [])
        meta, _ = split((self.p.entities / "P.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["type"], "organization")

    def test_entity_url_from_creator(self):
        self.two_saves(name="Lauren Chen")
        self.p.tagging.mkdir(parents=True)
        (self.p.tagging / "creator-people.json").write_text('{"thelaurenchen": "Lauren Chen"}',
                                                          encoding="utf-8")
        self.apply({"Lauren Chen": {"kind": "person", "sentence": "s", "sources": []}})
        meta, _ = split((self.p.entities / "Lauren Chen.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["url"], "https://www.instagram.com/thelaurenchen/")
        self.assertIn("thelaurenchen", meta["aliases"])

    def test_apply_domain_union(self):
        self.save("One", "S1", people=["P"], domain=["Coding"])
        self.save("Two", "S2", people=["P"], domain=["AI"])
        self.apply({"P": {"kind": "person", "sentence": "s", "sources": []}})
        meta, _ = split((self.p.entities / "P.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["domain"], ["[[AI]]", "[[Coding]]"])

    def test_apply_existing_page_only_appended(self):
        self.save("One", "S1", people=["Known"])
        page = write_note(self.p.concepts, "Known", {"type": "concept"}, "# Known\nMy text.\n")
        original = page.read_text(encoding="utf-8")
        counts = self.apply({})
        self.assertEqual(counts["embedded"], 1)
        updated = page.read_text(encoding="utf-8")
        self.assertTrue(updated.startswith(original))
        self.assertIn(EMBED_HEADING, updated)

    def test_people_notes_never_edited(self):
        self.two_saves(name="Friend")
        note = write_note(self.p.people, "Friend", {"type": "person"}, "# Friend\n")
        before = note.read_bytes()
        plan = self.plan()
        self.assertEqual((plan["new"], plan["needs_embed"]), ([], []))
        self.apply({"Friend": {"kind": "person", "sentence": "s", "sources": []}})
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(self.files(self.p.entities), [])

    def test_index_lines_replace_placeholder(self):
        self.two_saves(field="themes")
        self.apply({"P": {"kind": "concept", "sentence": "An idea.", "sources": []}})
        text = self.p.index_md.read_text(encoding="utf-8")
        concepts = text.split("## Concepts\n", 1)[1].split("## Synthesis", 1)[0]
        self.assertEqual(concepts, "- [[P]] — An idea.\n\n")
        self.assertIn("## Entities\n*None yet. People", text)

    def test_vocab(self):
        self.save("One", "S1", people=["P"])
        write_note(self.p.entities, "Known", {"type": "person", "aliases": ["K"]})
        self.p.tagging.mkdir(parents=True)
        (self.p.tagging / "creator-people.json").write_text('{"im_roy_lee": "Roy Lee"}', encoding="utf-8")
        vocab = cmd_vocab(self.p)
        self.assertEqual(vocab["pages"], {"Known": {"type": "person", "aliases": ["K"]}})
        self.assertEqual(vocab["linked"], {"P": 1})
        self.assertEqual(vocab["domains"], ["AI", "Coding"])
        self.assertEqual(vocab["creators"], {"im_roy_lee": "Roy Lee"})

    def make_layer(self, hub):
        """A domain folder as the vault has them now: <vault>/<Domain>/wiki/ with its index."""
        layer = self.p.vault / hub / "wiki"
        layer.mkdir(parents=True)
        (layer / f"{hub} index.md").write_text(
            f"# {hub} index\n\n## Entities\n*None yet.*\n\n## Concepts\n*None yet.*\n", encoding="utf-8")
        return layer

    def test_old_wiki_layer_path_ignored(self):
        (self.p.wiki / "Coding").mkdir(parents=True)  # the old wiki/<Domain>/ layout only
        self.two_saves(name="Python", field="subjects", domain=["Coding"])
        self.apply({"Python": {"kind": "tool", "sentence": "A language.", "sources": []}})
        self.assertTrue((self.p.entities / "Python.md").exists())

    def test_vault_notes_skips_x_raw(self):
        write_note(self.p.vault / "raw" / "X", "2120094207604035595", {"type": "source"})
        self.assertNotIn("2120094207604035595", vault_notes(self.p.vault))

    def test_apply_layer_domain_goes_to_layer(self):
        layer = self.make_layer("Coding")
        self.two_saves(name="Python", field="subjects", domain=["Coding"])
        self.apply({"Python": {"kind": "tool", "sentence": "A language.", "sources": []}})
        self.assertTrue((layer / "entities" / "Python.md").exists())
        self.assertEqual(self.files(self.p.entities), [])
        self.assertIn("- [[Python]] — A language.", (layer / "Coding index.md").read_text(encoding="utf-8"))
        self.assertNotIn("[[Python]]", self.p.index_md.read_text(encoding="utf-8"))

    def test_first_domain_without_layer_stays_shared(self):
        self.make_layer("Coding")
        self.two_saves(field="themes")
        self.apply({"P": {"kind": "concept", "sentence": "s", "sources": [], "domain": ["AI", "Coding"]}})
        self.assertTrue((self.p.concepts / "P.md").exists())

    def test_layer_pages_count_as_existing(self):
        layer = self.make_layer("Coding")
        write_note(layer / "concepts", "Recursion", {"type": "concept"}, "# Recursion\n")
        self.two_saves(name="recursion", field="themes")
        plan = self.plan()
        self.assertEqual(plan["new"], [])
        self.assertEqual(plan["needs_embed"], [str(layer / "concepts" / "Recursion.md")])

    def test_domain_union_most_common_first(self):
        self.save("One", "S1", people=["P"], domain=["Coding"])
        self.save("Two", "S2", people=["P"], domain=["Coding"])
        self.save("Three", "S3", people=["P"], domain=["AI"])
        self.apply({"P": {"kind": "person", "sentence": "s", "sources": []}})
        meta, _ = split((self.p.entities / "P.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["domain"], ["[[Coding]]", "[[AI]]"])

    def test_plan_reports_vault_conflict(self):
        self.two_saves(name="AI", field="themes")
        plan = self.plan()
        self.assertEqual(plan["new"], [])
        self.assertEqual([c["name"] for c in plan["conflicts"]], ["AI"])
        self.assertTrue(plan["conflicts"][0]["path"].endswith("AI.md"))

    def test_apply_refuses_vault_conflict(self):
        self.two_saves(name="AI", field="themes")
        with self.assertRaisesRegex(ValueError, "AI"):
            self.apply({"AI": {"kind": "concept", "sentence": "s", "sources": []}})
        self.assertEqual(self.files(self.p.concepts), [])

    def test_apply_rejects_case_duplicate_names(self):
        self.two_saves(name="Collectibles", field="themes")
        with self.assertRaisesRegex(ValueError, "ollectibles"):
            self.apply({"Collectibles": {"kind": "concept", "sentence": "s", "sources": []},
                        "collectibles": {"kind": "concept", "sentence": "s", "sources": []}})
        self.assertEqual(self.files(self.p.concepts), [])

    def test_apply_repairs_missing_index_line(self):
        self.two_saves(field="themes")
        write_note(self.p.concepts, "P", {"type": "concept", "created_by": "claude"}, "# P\n")
        self.apply({"P": {"kind": "concept", "sentence": "An idea.", "sources": []}})
        self.assertIn("- [[P]] — An idea.", self.p.index_md.read_text(encoding="utf-8"))

    def test_apply_source_quotes(self):
        self.two_saves(field="themes")
        self.apply({"P": {"kind": "concept", "sentence": "s",
                          "sources": [{"page": "One", "quote": "Was $20"}]}})
        meta, body = split((self.p.concepts / "P.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["sources"], ["[[One]]"])
        self.assertIn('- [[One]]: "Was \\$20"', body)

    def test_apply_rejects_quote_with_contact(self):
        self.two_saves(field="themes")
        with self.assertRaisesRegex(ValueError, "contact"):
            self.apply({"P": {"kind": "concept", "sentence": "s",
                              "sources": [{"page": "One", "quote": "mail a@b.com"}]}})

    def test_apply_rejects_bad_entry_types(self):
        self.two_saves(field="themes")
        with self.assertRaisesRegex(ValueError, "P: aliases"):
            self.apply({"P": {"kind": "concept", "sentence": "s", "sources": [], "aliases": "MF"}})
        with self.assertRaisesRegex(ValueError, "P: sentence"):
            self.apply({"P": {"kind": "concept", "sentence": "two\nlines", "sources": []}})


class IndexLineTests(unittest.TestCase):
    def test_index_lines_skip_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.md"
            index.write_text(INDEX, encoding="utf-8")
            self.assertEqual(add_index_lines(index, "## Entities", ["- [[A]] — a"]), 1)
            self.assertEqual(add_index_lines(index, "## Entities", ["- [[A]] — a", "- [[B]] — b"]), 1)
            entities = index.read_text(encoding="utf-8").split("## Entities\n", 1)[1].split("## Concepts")[0]
            self.assertEqual(entities, "- [[A]] — a\n- [[B]] — b\n\n")


if __name__ == "__main__":
    unittest.main()
