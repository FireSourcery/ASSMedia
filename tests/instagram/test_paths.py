"""assmedia.instagram.cli.paths: every Instagram path from the config."""
import re
import unittest
from pathlib import Path

from assmedia.core.config import InstagramSettings
from assmedia.instagram.cli import paths
from tests.core.fixtures import config_with

PKG = Path(__file__).resolve().parents[2] / "assmedia" / "instagram"


class PathsTests(unittest.TestCase):
    CFG = config_with(raw="D:/r", state="D:/s", vault="D:/v", ffmpeg="D:/f.exe",
                      instagram=InstagramSettings(saved_account="me"))

    def test_paths_from_config(self):
        p = paths(self.CFG)
        self.assertEqual((p.items, p.thumbs_dir, p.tagging, p.build),
                         (Path("D:/r/Instagram/items"), Path("D:/r/Instagram/thumbs"), Path("D:/s/Instagram/tagging"),
                          Path("D:/s/Instagram/build")))
        self.assertEqual((p.items_url, p.thumbs_url), ("file:///D:/r/Instagram/items", "file:///D:/r/Instagram/thumbs"))
        self.assertEqual((p.vault, p.pages, p.index_md),
                         (Path("D:/v"), Path("D:/v/wiki/sources/Instagram"), Path("D:/v/wiki/index.md")))
        self.assertEqual(p.ffmpeg, Path("D:/f.exe"))
        self.assertEqual([c.name for c in p.collections], ["Instagram", "X"])
        self.assertEqual(p.collections[1].items, Path("D:/r/X/items"))  # X seen in full, from the one config

    def test_vault_thumb_mode(self):
        self.assertEqual(paths(self.CFG, "vault").thumbs_dir, Path("D:/v/raw/Instagram/_thumbs"))

    def test_no_instance_values_in_code(self):
        pattern = re.compile(r"V:[\\/]|firesourcery|firefox|Vault0", re.IGNORECASE)
        hits = [f"{path.name}:{n}" for path in sorted(PKG.glob("*.py"))
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
