import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from unittest import mock

from assmedia.core import fsread
from assmedia.instagram import cli
from assmedia.instagram.cli import cmd_build, cmd_export, pending
from assmedia.core.yamlfm import split
from tests.core.fixtures import make_paths, make_post_folder


def read_calls(run) -> list[list[Path]]:
    """The paths of each fsread.read_texts call made while `run()` runs."""
    calls, real = [], fsread.read_texts

    def recording(paths, *a, **k):
        calls.append(list(paths))
        return real(paths, *a, **k)

    with mock.patch("assmedia.core.fsread.read_texts", recording):
        run()
    return calls


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        vault = root / "vault"
        self.p = make_paths(root, ffmpeg=root / "no-ffmpeg.exe")
        self.p.items.mkdir()
        self.p.domains.mkdir(parents=True)
        for hub in ("AI", "Coding"):
            (self.p.domains / f"{hub}.md").write_text("", encoding="utf-8")

    def add_post(self, sc, files=None, **data):
        return make_post_folder(self.p.items, sc, [f"{sc}_01.mp4"] if files is None else files, data)

    def tags_file(self, entries):
        path = Path(self._tmp.name) / "tags.json"
        path.write_text(json.dumps(entries), encoding="utf-8")
        return path

    def pages(self):
        return sorted(self.p.pages.glob("*.md")) if self.p.pages.exists() else []


class BuildTests(CliTestCase):
    def test_build_creates_page_without_raw_copy(self):
        self.add_post("X")
        counts, _ = cmd_build(self.p, self.tags_file({"X": {"title": "A thing"}}), date(2026, 11, 11))
        self.assertEqual(counts["created"], 1)
        self.assertFalse((self.p.vault / "raw").exists())
        [page] = self.pages()
        self.assertEqual(page.name, "A thing (someone).md")
        text = page.read_text(encoding="utf-8")
        self.assertNotIn("[[X]]", text)
        self.assertTrue(text.endswith("\n> a caption\n"))

    def test_build_skips_existing_page(self):
        self.add_post("X")
        self.p.pages.mkdir(parents=True)
        existing = self.p.pages / "Mine.md"
        existing.write_bytes(b'---\nshortcode: "X"\npeople:\n  - "[[Hand Added]]"\n---\nmy edits\n')
        before = existing.read_bytes()
        counts, _ = cmd_build(self.p, self.tags_file({"X": {"title": "Other"}}), date(2026, 11, 11))
        self.assertEqual(counts["skipped"], 1)
        self.assertEqual(existing.read_bytes(), before)
        self.assertEqual(self.pages(), [existing])

    def test_build_domain_written(self):
        self.add_post("X")
        cmd_build(self.p, self.tags_file({"X": {"title": "T", "domain": ["coding"]}}), date(2026, 11, 11))
        meta, _ = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["domain"], ["[[Coding]]"])

    def test_build_unknown_domain_writes_nothing(self):
        self.add_post("X")
        counts, messages = cmd_build(self.p, self.tags_file({"X": {"title": "T", "domain": ["Cooking"]}}),
                                     date(2026, 11, 11))
        self.assertEqual(counts["created"], 0)
        self.assertEqual(self.pages(), [])
        self.assertFalse((self.p.vault / "raw" / "X.md").exists())
        self.assertTrue(any(m.startswith("X:") and "Cooking" in m for m in messages))

    def test_build_invalid_tag_writes_nothing(self):
        self.add_post("X")
        counts, messages = cmd_build(self.p, self.tags_file({"X": {"people": ["A|B"]}}), date(2026, 11, 11))
        self.assertEqual(counts["created"], 0)
        self.assertFalse((self.p.vault / "raw" / "X.md").exists())
        self.assertEqual(self.pages(), [])
        self.assertTrue(any(m.startswith("X:") for m in messages))

    def test_creator_people_merged(self):
        self.add_post("X", username="thelaurenchen")
        cmd_build(self.p, self.tags_file({"X": {"title": "T", "creator_person": "Lauren Chen"}}),
                  date(2026, 11, 11))
        mapping = json.loads((self.p.tagging / "creator-people.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping, {"thelaurenchen": "Lauren Chen"})

    def test_build_writes_lf_newlines(self):
        self.add_post("X")
        cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        self.assertNotIn(b"\r\n", self.pages()[0].read_bytes())

    def test_build_title_collision_within_batch(self):
        self.add_post("X")
        self.add_post("Y")
        cmd_build(self.p, self.tags_file({"X": {"title": "Same"}, "Y": {"title": "Same"}}),
                  date(2026, 11, 11))
        self.assertEqual([p.name for p in self.pages()],
                         ["Same (someone) - Y.md", "Same (someone).md"])

    def test_build_counts_missing_thumbnail(self):
        self.add_post("X")
        counts, messages = cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        self.assertEqual(counts["thumb_failed"], 1)
        meta, _ = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertIsNone(meta["thumbnail"])

    def test_build_saved_date_is_the_download_day(self):
        self.add_post("X")
        cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        meta, _ = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["saved"], date.today().isoformat())
        self.assertNotIn("saved_rank", meta)


    def test_build_reuses_existing_spelling(self):
        self.add_post("OLD")
        self.add_post("X")
        cmd_build(self.p, self.tags_file({"OLD": {"title": "Old", "people": ["Miss Fortune"]}}),
                  date(2026, 11, 11))
        cmd_build(self.p, self.tags_file({"X": {"title": "New", "people": ["miss fortune"]}}),
                  date(2026, 11, 11))
        meta, _ = split((self.p.pages / "New (someone).md").read_text(encoding="utf-8"))
        self.assertEqual(meta["people"], ["[[Miss Fortune]]"])

    def creators(self):
        return json.loads((self.p.tagging / "creator-people.json").read_text(encoding="utf-8"))

    def test_creator_mapping_saved_for_skipped_posts(self):
        self.add_post("X", username="laurenc")
        self.p.pages.mkdir(parents=True)
        (self.p.pages / "Mine.md").write_text('---\nshortcode: "X"\n---\n', encoding="utf-8")
        cmd_build(self.p, self.tags_file({"X": {"title": "T", "creator_person": "Lauren Chen"}}),
                  date(2026, 11, 11))
        self.assertEqual(self.creators(), {"laurenc": "Lauren Chen"})

    def test_creator_mapping_saved_when_build_crashes(self):
        self.add_post("X", username="laurenc")
        self.add_post("Y")
        real_render = cli.render_page

        def render_then_fail(post, *args, **kwargs):
            if post.shortcode == "Y":
                raise OSError("disk full")
            return real_render(post, *args, **kwargs)

        with mock.patch.object(cli, "render_page", side_effect=render_then_fail):
            with self.assertRaises(OSError):
                cmd_build(self.p, self.tags_file({"X": {"title": "T", "creator_person": "Lauren Chen"},
                                                  "Y": {"title": "U"}}), date(2026, 11, 11))
        self.assertEqual(self.creators(), {"laurenc": "Lauren Chen"})

    def test_creator_mapping_keeps_first_name(self):
        self.add_post("X", username="im_roy_lee")
        self.p.tagging.mkdir(parents=True)
        (self.p.tagging / "creator-people.json").write_text('{"im_roy_lee": "Roy Lee"}', encoding="utf-8")
        _, messages = cmd_build(self.p, self.tags_file(
            {"X": {"title": "T", "creator_person": "Roy (Chungin) Lee"}}), date(2026, 11, 11))
        meta, _ = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["people"], ["[[Roy Lee]]"])
        self.assertEqual(self.creators(), {"im_roy_lee": "Roy Lee"})
        self.assertTrue(any(m.startswith("X:") and "Roy Lee" in m for m in messages))

    def test_creator_person_joins_batch_index(self):
        self.add_post("X", username="im_roy_lee")
        self.add_post("Y")
        cmd_build(self.p, self.tags_file({"X": {"title": "A", "creator_person": "Roy Lee"},
                                          "Y": {"title": "B", "people": ["roy lee"]}}),
                  date(2026, 11, 11))
        metas = {split(p.read_text(encoding="utf-8"))[0]["shortcode"]: split(p.read_text(encoding="utf-8"))[0]
                 for p in self.pages()}
        self.assertEqual(metas["Y"]["people"], ["[[Roy Lee]]"])

    def test_build_skips_page_with_bom(self):
        self.add_post("X")
        self.p.pages.mkdir(parents=True)
        (self.p.pages / "Mine.md").write_bytes('﻿---\nshortcode: "X"\n---\n'.encode("utf-8"))
        counts, _ = cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        self.assertEqual((counts["skipped"], len(self.pages())), (1, 1))

    def test_build_same_batch_spelling(self):
        self.add_post("X")
        self.add_post("Y")
        cmd_build(self.p, self.tags_file({"X": {"title": "A", "people": ["Miss Fortune"]},
                                          "Y": {"title": "B", "people": ["miss fortune"]}}),
                  date(2026, 11, 11))
        people = {split(p.read_text(encoding="utf-8"))[0]["shortcode"]:
                  split(p.read_text(encoding="utf-8"))[0]["people"] for p in self.pages()}
        self.assertEqual(people, {"X": ["[[Miss Fortune]]"], "Y": ["[[Miss Fortune]]"]})

    def test_build_uses_concept_alias(self):
        self.add_post("X")
        self.p.entities.mkdir(parents=True)
        (self.p.entities / "Lauren Chen.md").write_text('---\naliases:\n  - "thelaurenchen"\n---\n',
                                                         encoding="utf-8")
        cmd_build(self.p, self.tags_file({"X": {"title": "T", "people": ["thelaurenchen"]}}),
                  date(2026, 11, 11))
        meta, _ = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["people"], ["[[Lauren Chen]]"])


class UpdateMediaTests(CliTestCase):
    PLAYER = '<video controls preload="metadata" width="360" src="file:///D:/m/raw/Instagram/items/X/X_02.mp4"></video>'
    PHOTO = "![](file:///D:/m/raw/Instagram/items/X/X_01.jpg)"
    EXPECTED_BODY = "\n# T (someone)\n\n" + PHOTO + "\n\n" + PLAYER + "\n\n> a caption\n"

    def legacy_page(self, with_players: bool, extra_line: str | None = None):
        """A carousel page in an older layout: thumbnail, (players), links, View on Instagram."""
        self.add_post("X", files=["X_01.jpg", "X_02.mp4"])
        cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        page = self.pages()[0]
        meta_text = page.read_text(encoding="utf-8").split("\n# ", 1)[0]
        body = ["# T (someone)", "", "![](file:///D:/m/raw/Instagram/thumbs/X.jpg)", ""]
        if with_players:
            body += [self.PLAYER, ""]
        body += ["- [Open photo 1](file:///D:/m/raw/Instagram/items/X/X_01.jpg)",
                 "- [Open video 2](file:///D:/m/raw/Instagram/items/X/X_02.mp4)",
                 "- [View on Instagram](https://www.instagram.com/p/X/)", "", "> a caption", ""]
        if extra_line:
            body.insert(3, extra_line)
        page.write_text(meta_text + "\n" + "\n".join(body), encoding="utf-8", newline="\n")
        return page

    def body(self, page):
        return split(page.read_text(encoding="utf-8"))[1]

    def test_update_media_legacy_without_players(self):
        page = self.legacy_page(with_players=False)
        counts = cli.cmd_update_media(self.p)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(self.body(page), self.EXPECTED_BODY)

    def test_update_media_legacy_with_players(self):
        page = self.legacy_page(with_players=True)
        cli.cmd_update_media(self.p)
        self.assertEqual(self.body(page), self.EXPECTED_BODY)

    def test_update_media_keeps_frontmatter(self):
        page = self.legacy_page(with_players=True)
        before = split(page.read_text(encoding="utf-8"))[0]
        cli.cmd_update_media(self.p)
        self.assertEqual(split(page.read_text(encoding="utf-8"))[0], before)

    def test_update_media_idempotent(self):
        self.legacy_page(with_players=True)
        cli.cmd_update_media(self.p)
        counts = cli.cmd_update_media(self.p)
        self.assertEqual((counts["updated"], counts["already"]), (0, 1))

    def test_new_page_is_already_current(self):
        self.add_post("X", files=["X_01.jpg", "X_02.mp4"])
        cmd_build(self.p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        self.assertEqual(cli.cmd_update_media(self.p)["already"], 1)

    def test_update_media_skips_user_text(self):
        page = self.legacy_page(with_players=True, extra_line="My own note about this save")
        before = page.read_bytes()
        counts = cli.cmd_update_media(self.p)
        self.assertEqual(counts["skipped_edited"], 1)
        self.assertEqual(page.read_bytes(), before)

    def test_update_media_dry_run_writes_nothing(self):
        page = self.legacy_page(with_players=True)
        before = page.read_bytes()
        counts = cli.cmd_update_media(self.p, dry_run=True)
        self.assertEqual(counts["updated"], 1)
        self.assertEqual(page.read_bytes(), before)


class PendingTests(CliTestCase):
    def test_pending_excludes_incomplete(self):
        self.add_post("X", files=[])
        todo, incomplete = pending(self.p)
        self.assertEqual(todo, [])
        self.assertEqual(incomplete, ["X"])

    def test_pending_oldest_download_first(self):
        for sc in ("NEW", "OLD", "MID"):
            self.add_post(sc)
        todo, _ = pending(self.p)
        self.assertEqual(len(todo), 3)
        self.assertEqual(sorted(todo, key=lambda x: x.folder.stat().st_ctime), todo)

    def test_export_writes_rows(self):
        self.add_post("X", description="cap", tags=["#t"])
        out = cmd_export(self.p, "first", 5)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8")), [{
            "shortcode": "X", "username": "someone", "fullname": "Some One", "caption": "cap",
            "hashtags": ["#t"], "media": "video"}])


class ConfiguredUrlTests(CliTestCase):
    def test_build_links_configured_urls(self):
        """A new page's thumbnail and media links name the configured folders, not a fixed root."""
        p = replace(self.p, items_url="file:///Z:/I", thumbs_url="file:///Z:/T")
        self.add_post("X", files=["X_01.jpg"])
        p.thumbs_dir.mkdir(parents=True)
        (p.thumbs_dir / "X.jpg").write_bytes(b"jpg")  # an existing thumbnail is kept, so no ffmpeg is needed
        cmd_build(p, self.tags_file({"X": {"title": "T"}}), date(2026, 11, 11))
        meta, body = split(self.pages()[0].read_text(encoding="utf-8"))
        self.assertEqual(meta["thumbnail"], "file:///Z:/T/X.jpg")
        self.assertIn("![](file:///Z:/I/X/X_01.jpg)", body)
        self.assertNotIn("D:/m/raw/Instagram", body)  # the fixtures' default


class DataSplitTests(CliTestCase):
    def test_export_goes_to_build(self):
        self.add_post("X")
        out = cmd_export(self.p, "b1", 5)
        self.assertEqual(out, self.p.build / "export" / "b1.json")
        self.assertTrue(out.is_file())

    def test_creator_map_in_tagging(self):
        self.add_post("X", username="laurenc")
        cmd_build(self.p, self.tags_file({"X": {"title": "T", "creator_person": "Lauren Chen"}}), date(2026, 11, 11))
        mapping = json.loads((self.p.tagging / "creator-people.json").read_text(encoding="utf-8"))
        self.assertEqual(mapping, {"laurenc": "Lauren Chen"})
        self.assertFalse(self.p.build.exists())



class VaultUniqueTitleTests(CliTestCase):
    def test_title_avoids_names_elsewhere_in_vault(self):
        from tests.core.fixtures import write_note
        self.add_post("AAA")
        write_note(self.p.vault / "wiki" / "sources" / "X", "A thing (someone)", {"tweet_id": "1"})
        counts, _ = cmd_build(self.p, self.tags_file({"AAA": {"title": "A thing"}}), date(2026, 11, 11))
        self.assertEqual(counts["created"], 1)
        self.assertTrue((self.p.pages / "A thing (someone) - AAA.md").exists())


if __name__ == "__main__":
    unittest.main()
