"""assmedia.x.cli.default_xpaths: every X path from the config."""
import re
import unittest
from pathlib import Path

from assmedia.x.cli import default_xpaths
from tests.core.fixtures import config_with

PKG = Path(__file__).resolve().parents[2] / "assmedia" / "x"


class PathsTests(unittest.TestCase):
    def test_default_xpaths_from_config(self):
        xp = default_xpaths(config_with(raw="D:/r", state="D:/s", vault="D:/v", ffmpeg="D:/f.exe"))
        self.assertEqual((xp.core.items, xp.threads, xp.core.thumbs_dir),
                         (Path("D:/r/X/items"), Path("D:/r/X/threads"), Path("D:/r/X/thumbs")))
        self.assertEqual((xp.crawl, xp.tagging, xp.build, xp.core.tagging, xp.core.build),
                         (Path("D:/s/X/_crawl"), Path("D:/s/X/tagging"), Path("D:/s/X/build"),
                          Path("D:/s/X/tagging"), Path("D:/s/X/build")))
        self.assertEqual((xp.core.pages, xp.core.ffmpeg), (Path("D:/v/wiki/sources/X"), Path("D:/f.exe")))
        self.assertEqual(xp.gallery_conf, Path("D:/s/X/_crawl/gallery-dl.conf"))  # the filled-in copy
        (x_col,) = [c for c in xp.core.collections if c.name == "X"]
        self.assertEqual(x_col.creators, Path("D:/s/X/tagging/creator-people.json"))
        self.assertEqual(xp.own_accounts, frozenset({"me"}))

    def test_space_in_raw_is_encoded(self):
        xp = default_xpaths(config_with(raw="D:/My Media/raw"))
        self.assertEqual(xp.core.items_url, "file:///D:/My%20Media/raw/X/items")

    def test_no_instance_values_in_code(self):
        pattern = re.compile(r"V:[\\/]|firesourcery|firefox|Vault0", re.IGNORECASE)
        hits = [f"{path.name}:{n}" for path in sorted(PKG.glob("*.py"))
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
