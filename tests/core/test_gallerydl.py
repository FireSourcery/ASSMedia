"""The gallery-dl configs hold behaviour only; paths and the browser are filled in from the config before each run."""
import json
import re
import tempfile
import unittest
from pathlib import Path

from assmedia.core.gallerydl import fill, write_conf
from assmedia.instagram import update as ig_update
from assmedia.x import update as x_update
from tests.core.fixtures import config_with

PKG = Path(__file__).resolve().parents[2] / "assmedia"


def load_template(platform: str) -> dict:
    return json.loads((PKG / platform / "gallery-dl.conf").read_text(encoding="utf-8"))


def path_values(node) -> list[str]:
    """Every string in a gallery-dl config that names a drive: the paths it was filled in with."""
    if isinstance(node, dict):
        return [v for value in node.values() for v in path_values(value)]
    if isinstance(node, list):
        return [v for value in node for v in path_values(value)]
    return [node] if isinstance(node, str) and re.match(r"[A-Za-z]:/", node) else []


def metadata_writers(node) -> list[dict]:
    """Every metadata post-processor in a gallery-dl config: the blocks that write the JSON files."""
    if isinstance(node, dict):
        own = [node] if node.get("name") == "metadata" else []
        return own + [w for value in node.values() for w in metadata_writers(value)]
    if isinstance(node, list):
        return [w for value in node for w in metadata_writers(value)]
    return []


class LineEndingTests(unittest.TestCase):
    def test_every_json_writer_uses_lf(self):
        """gallery-dl writes in text mode, so without `newline` its JSON gets CRLF on Windows and LF elsewhere."""
        found = 0
        for name in ("x/gallery-dl.conf", "x/gallery-dl-list.conf", "instagram/gallery-dl.conf"):
            for writer in metadata_writers(json.loads((PKG / name).read_text(encoding="utf-8"))):
                found += 1
                self.assertEqual(writer.get("newline"), "\n", f"{name}: {writer.get('filename')}")
        self.assertEqual(found, 5)  # X: bookmark, quoted, thread; X list; Instagram


class FillTests(unittest.TestCase):
    def test_format_fields_and_paths_survive(self):
        out = fill({"extractor": {"twitter": {"filename": "{tweet_id}_{num:>02}.{extension}"}}},
                   {("extractor", "base-directory"): "D:/m/raw/X/items/"})
        self.assertEqual(out["extractor"]["twitter"]["filename"], "{tweet_id}_{num:>02}.{extension}")
        self.assertEqual(out["extractor"]["base-directory"], "D:/m/raw/X/items/")

    def test_missing_dicts_are_made_and_the_template_is_untouched(self):
        template = {"extractor": {}}
        out = fill(template, {("output", "logfile", "path"): "D:/s/log"})
        self.assertEqual(out["output"]["logfile"]["path"], "D:/s/log")
        self.assertEqual(template, {"extractor": {}})

    def test_a_list_index_must_exist(self):
        with self.assertRaises(IndexError):
            fill({"pps": []}, {("pps", 0, "directory"): "D:/s"})

    def test_write_conf_makes_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "t.conf"
            template.write_text('{"extractor": {}}', encoding="utf-8")
            out = write_conf(template, {("extractor", "base-directory"): "D:/m/raw/X/items/"},
                             Path(tmp) / "state" / "X" / "_crawl" / "gallery-dl.conf")
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["extractor"]["base-directory"],
                             "D:/m/raw/X/items/")


class PlatformConfTests(unittest.TestCase):
    def test_every_x_path_under_raw_or_state(self):
        conf = fill(load_template("x"), x_update.conf_values(config_with(raw="D:/m/raw", state="D:/m/state")))
        values = path_values(conf)
        self.assertEqual(len(values), 5)  # base-directory, archive, threads, log, errors
        for value in values:
            self.assertTrue(value.startswith(("D:/m/raw/", "D:/m/state/")), value)
        self.assertEqual(conf["extractor"]["twitter"]["cookies"], ["firefox"])
        self.assertEqual(conf["extractor"]["twitter"]["tweet"]["postprocessors"][0]["directory"], "D:/m/raw/X/threads")

    def test_every_instagram_path_under_raw_or_state(self):
        conf = fill(load_template("instagram"), ig_update.conf_values(config_with(raw="D:/m/raw", state="D:/m/state")))
        values = path_values(conf)
        self.assertEqual(len(values), 4)  # base-directory, archive, log, errors
        for value in values:
            self.assertTrue(value.startswith(("D:/m/raw/", "D:/m/state/")), value)
        self.assertEqual(conf["extractor"]["instagram"]["cookies"], ["firefox"])

    def test_cookies_come_from_the_config(self):
        conf = fill(load_template("x"), x_update.conf_values(config_with(cookies="chrome")))
        self.assertEqual(conf["extractor"]["twitter"]["cookies"], ["chrome"])

    def test_space_in_state(self):
        conf = fill(load_template("x"), x_update.conf_values(config_with(state="D:/My Media/state")))
        self.assertEqual(conf["extractor"]["twitter"]["archive"], "D:/My Media/state/X/_crawl/gallery-dl-archive.sqlite3")

    def test_templates_hold_no_paths_or_browser(self):
        for name in ("x/gallery-dl.conf", "x/gallery-dl-list.conf", "instagram/gallery-dl.conf"):
            text = (PKG / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"[A-Za-z]:/")
            self.assertNotIn("firefox", text)
            self.assertIn("{", text)  # gallery-dl's own format fields are still there


if __name__ == "__main__":
    unittest.main()
