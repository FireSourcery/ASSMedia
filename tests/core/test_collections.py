"""Concept and entity pages shared by several collections (Instagram saves, X bookmarks)."""
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from assmedia.core.paths import Paths, collections
from assmedia.core.collection import collections_of, instagram, x
from assmedia.core.concepts import cmd_concepts_apply, cmd_concepts_plan, cmd_vocab, embed_block, ensure_embed
from assmedia.core.yamlfm import split
from tests.core.fixtures import config_with, make_paths, make_post_folder, write_note

INSTAGRAM_BLOCK = (
    "## Instagram saves\n\n```base\nfilters:\n  and:\n"
    '    - file.inFolder("wiki/sources/Instagram")\n    - file.hasLink(this.file)\n'
    "views:\n  - type: cards\n    name: Saves\n    image: note.thumbnail\n    order:\n"
    "      - file.name\n      - description\n```\n")
INDEX = "# Wiki index\n\n## Entities\n*None yet.*\n\n## Concepts\n*None yet.*\n"


class CollectionTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        vault = root / "vault"
        self.ig = instagram(vault / "pages", root / "items", root / "tagging")
        self.xc = x(vault / "xpages", root / "xitems", root / "xdata")
        self.p = make_paths(root, ffmpeg=root / "none.exe", collections=(self.ig, self.xc))
        self.p.domains.mkdir(parents=True)
        (self.p.domains / "AI.md").write_text("", encoding="utf-8")
        self.p.index_md.write_text(INDEX, encoding="utf-8")

    def save_ig(self, title, sc, **fields):
        make_post_folder(self.p.items, sc, [f"{sc}_01.mp4"], {"description": "ig caption"})
        return write_note(self.ig.pages, title, {"shortcode": sc, **self._links(fields)})

    def save_x(self, title, tweet_id, content="tweet text", **fields):
        folder = self.xc.items / tweet_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{tweet_id}.json").write_text(json.dumps({"tweet_id": int(tweet_id), "content": content}),
                                                 encoding="utf-8")
        return write_note(self.xc.pages, title, {"tweet_id": tweet_id, **self._links(fields)})

    @staticmethod
    def _links(fields):
        return {name: [f"[[{v}]]" for v in values] for name, values in fields.items()}

    def plan(self):
        return json.loads(cmd_concepts_plan(self.p, "t").read_text(encoding="utf-8"))

    def apply(self, entries):
        path = Path(self._tmp.name) / "concepts.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return cmd_concepts_apply(self.p, path, date(2026, 11, 11))


class EmbedBlockTests(CollectionTestCase):
    def test_instagram_embed_unchanged(self):
        self.assertEqual(embed_block(self.ig), INSTAGRAM_BLOCK)
        self.assertEqual(embed_block(), INSTAGRAM_BLOCK)

    def test_x_embed_block(self):
        block = embed_block(self.xc)
        self.assertTrue(block.startswith("## X bookmarks\n"))
        self.assertIn('file.inFolder("wiki/sources/X")', block)
        self.assertIn("name: Bookmarks", block)

    def test_x_embed_inserted_after_instagram_block(self):
        text = "# Known\n\n" + INSTAGRAM_BLOCK + "\n## Sources\n- \n"
        out = ensure_embed(text, self.xc, (self.ig, self.xc))
        self.assertIn(INSTAGRAM_BLOCK, out)
        self.assertLess(out.index("## Instagram saves"), out.index("## X bookmarks"))
        self.assertLess(out.index("## X bookmarks"), out.index("## Sources"))
        self.assertEqual(ensure_embed(out, self.xc, (self.ig, self.xc)), out)

    def test_x_embed_appended_without_instagram_block(self):
        out = ensure_embed("# Known\n", self.xc, (self.ig, self.xc))
        self.assertTrue(out.endswith(embed_block(self.xc)))
        self.assertNotIn("## Instagram saves", out)

    def test_collections_of_falls_back_to_instagram(self):
        p = Paths(**{**self.p.__dict__, "collections": ()})
        (only,) = collections_of(p)
        self.assertEqual((only.name, only.pages, only.heading), ("Instagram", p.pages, "## Instagram saves"))


class SharedPlanTests(CollectionTestCase):
    def test_threshold_counts_both_collections(self):
        self.save_ig("One", "S1", people=["P"])
        self.save_x("Two", "2120094207604035595", people=["P"])
        new = {e["name"]: e["count"] for e in self.plan()["new"]}
        self.assertEqual(new, {"P": 2})

    def test_plan_caption_from_x_json(self):
        self.save_x("Two", "2120094207604035595", content="what the tweet said", people=["P"])
        self.save_x("Three", "2120094207604035596", people=["P"])
        saves = {s["page"]: s for s in self.plan()["new"][0]["saves"]}
        self.assertEqual(saves["Two"]["caption"], "what the tweet said")
        self.assertEqual(saves["Two"]["collection"], "X")

    def test_needs_embed_per_collection(self):
        page = write_note(self.p.entities, "Known", {"type": "person"}, "# Known\n\n" + INSTAGRAM_BLOCK)
        self.save_ig("One", "S1", people=["Known"])
        self.save_x("Two", "2120094207604035595", people=["Known"])
        plan = self.plan()
        self.assertEqual(plan["needs_embed"], [str(page)])
        self.assertEqual(plan["needs_embed_detail"], [{"path": str(page), "collection": "X"}])


class SharedApplyTests(CollectionTestCase):
    def test_new_page_embeds_linking_collections(self):
        self.save_ig("One", "S1", people=["P"])
        self.save_x("Two", "2120094207604035595", people=["P"], themes=["Q"])
        self.save_x("Three", "2120094207604035596", themes=["Q"])
        self.apply({"P": {"kind": "person", "sentence": "s", "sources": []},
                    "Q": {"kind": "concept", "sentence": "s", "sources": []}})
        both = (self.p.entities / "P.md").read_text(encoding="utf-8")
        self.assertLess(both.index("## Instagram saves"), both.index("## X bookmarks"))
        only_x = (self.p.concepts / "Q.md").read_text(encoding="utf-8")
        self.assertIn("## X bookmarks", only_x)
        self.assertNotIn("## Instagram saves", only_x)

    def test_apply_appends_x_embed_to_existing_page(self):
        page = write_note(self.p.entities, "Known", {"type": "person"}, "# Known\n\n" + INSTAGRAM_BLOCK)
        self.save_x("Two", "2120094207604035595", people=["Known"])
        counts = self.apply({})
        text = page.read_text(encoding="utf-8")
        self.assertEqual(counts["embedded"], 1)
        self.assertEqual(text.count("## X bookmarks"), 1)
        self.assertEqual(text.count("## Instagram saves"), 1)

    def creators(self, c, mapping):
        c.creators.parent.mkdir(parents=True, exist_ok=True)
        c.creators.write_text(json.dumps(mapping), encoding="utf-8")

    def test_x_creator_url(self):
        self.creators(self.xc, {"elonmusk": "Elon Musk"})
        self.save_x("Two", "2120094207604035595", people=["Elon Musk"])
        self.save_x("Three", "2120094207604035596", people=["Elon Musk"])
        self.apply({"Elon Musk": {"kind": "person", "sentence": "s", "sources": []}})
        meta = split((self.p.entities / "Elon Musk.md").read_text(encoding="utf-8"))[0]
        self.assertEqual(meta["url"], "https://x.com/elonmusk")
        self.assertIn("elonmusk", meta["aliases"])

    def test_aliases_from_both_platforms(self):
        self.creators(self.ig, {"musk_ig": "Elon Musk"})
        self.creators(self.xc, {"elonmusk": "Elon Musk"})
        self.save_ig("One", "S1", people=["Elon Musk"])
        self.save_x("Two", "2120094207604035595", people=["Elon Musk"])
        self.apply({"Elon Musk": {"kind": "person", "sentence": "s", "sources": []}})
        meta = split((self.p.entities / "Elon Musk.md").read_text(encoding="utf-8"))[0]
        self.assertEqual(sorted(meta["aliases"]), ["elonmusk", "musk_ig"])
        self.assertEqual(meta["url"], "https://www.instagram.com/musk_ig/")

    def test_existing_page_gets_x_alias(self):
        page = write_note(self.p.entities, "Elon Musk", {"type": "person", "aliases": ["Elon"]},
                          "# Elon Musk\n\n" + INSTAGRAM_BLOCK)
        self.creators(self.xc, {"elonmusk": "Elon Musk"})
        self.save_x("Two", "2120094207604035595", people=["Elon Musk"])
        before = page.read_text(encoding="utf-8")
        counts = self.apply({})
        after = page.read_text(encoding="utf-8")
        self.assertEqual(split(after)[0]["aliases"], ["Elon", "elonmusk"])
        self.assertEqual(counts["aliased"], 1)
        self.assertTrue(after.startswith(before.split("aliases:")[0]))
        self.assertIn("# Elon Musk\n\n" + INSTAGRAM_BLOCK, after)

    def test_people_note_not_aliased(self):
        note = write_note(self.p.people, "Elon Musk", {"type": "person"}, "# Elon Musk\n")
        self.creators(self.xc, {"elonmusk": "Elon Musk"})
        self.save_x("Two", "2120094207604035595", people=["Elon Musk"])
        before = note.read_bytes()
        self.apply({})
        self.assertEqual(note.read_bytes(), before)

    def test_sources_may_be_x_pages(self):
        self.save_ig("One", "S1", people=["P"])
        self.save_x("Two", "2120094207604035595", people=["P"])
        self.apply({"P": {"kind": "person", "sentence": "s", "sources": ["Two"]}})
        self.assertIn("[[Two]]", (self.p.entities / "P.md").read_text(encoding="utf-8"))



class VaultOnlyXTests(CollectionTestCase):
    """Instagram's own runs see X only through the vault: X's pages, no X items, no X creator map."""

    def setUp(self):
        super().setUp()
        self.vault_x = x(self.xc.pages)
        self.p = replace(self.p, collections=(self.ig, self.vault_x))

    def test_collections_from_config(self):
        ig, xc = collections(config_with(raw="D:/r", state="D:/s", vault="D:/v"))
        self.assertEqual((ig.name, ig.items, ig.creators),
                         ("Instagram", Path("D:/r/Instagram/items"), Path("D:/s/Instagram/tagging/creator-people.json")))
        self.assertEqual((xc.name, xc.pages, xc.items), ("X", Path("D:/v/wiki/sources/X"), Path("D:/r/X/items")))

    def test_unconfigured_instagram_is_pages_only(self):
        ig, xc = collections(config_with(vault="D:/v", instagram=None))
        self.assertEqual((ig.pages, ig.items, ig.creators), (Path("D:/v/wiki/sources/Instagram"), None, None))
        self.assertEqual(xc.items, Path("D:/m/raw/X/items"))

    def test_unconfigured_platform_is_pages_only(self):
        ig, xc = collections(config_with(vault="D:/v", x=None))
        self.assertEqual((xc.pages, xc.items, xc.creators), (Path("D:/v/wiki/sources/X"), None, None))
        self.assertEqual(ig.items, Path("D:/m/raw/Instagram/items"))

    def test_plan_without_x_items(self):
        self.save_ig("One", "S1", people=["P"])
        self.save_x("Two", "2120094207604035595", content="what the tweet said", people=["P"])
        entry = self.plan()["new"][0]
        self.assertEqual((entry["name"], entry["count"]), ("P", 2))
        saves = {s["page"]: s for s in entry["saves"]}
        self.assertEqual(saves["Two"]["collection"], "X")
        self.assertEqual(saves["Two"]["caption"], "")
        self.assertEqual(saves["One"]["caption"], "ig caption")

    def test_apply_without_x_creators(self):
        self.creators(self.xc, {"elonmusk": "Elon Musk"})  # on disk, but the vault-only collection has no map
        self.save_ig("One", "S1", people=["Elon Musk"])
        self.save_x("Two", "2120094207604035595", people=["Elon Musk"])
        counts = self.apply({"Elon Musk": {"kind": "person", "sentence": "s", "sources": []}})
        text = (self.p.entities / "Elon Musk.md").read_text(encoding="utf-8")
        meta = split(text)[0]
        self.assertNotIn("elonmusk", meta.get("aliases") or [])
        self.assertIn("## Instagram saves", text)
        self.assertIn("## X bookmarks", text)
        self.assertEqual(counts["aliased"], 0)

    def test_vocab_and_needs_embed_with_vault_only_x(self):
        page = write_note(self.p.entities, "Known", {"type": "person"}, "# Known\n\n" + INSTAGRAM_BLOCK)
        self.save_ig("One", "S1", people=["Known"])
        self.save_x("Two", "2120094207604035595", people=["Known"])
        self.assertEqual(cmd_vocab(self.p)["linked"]["Known"], 2)
        self.assertEqual(self.plan()["needs_embed_detail"], [{"path": str(page), "collection": "X"}])

    creators = SharedApplyTests.creators


if __name__ == "__main__":
    unittest.main()
