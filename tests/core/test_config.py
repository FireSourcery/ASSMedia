"""assmedia.toml: every path, account and program one instance needs."""
import tempfile
import unittest
from pathlib import Path

from assmedia.core.config import (PLATFORMS, default_config_path, dirs, load_config, problems,
                                    split_config_arg)

ROOT = Path(__file__).resolve().parents[2]
X_SECTION = '[x]\nown = ["Me", "other"]\n'
IG_SECTION = '[instagram]\nsaved = "me"\n'
SAMPLE = ('[paths]\nraw = "D:/m/raw"\nstate = "D:/m/state"\nvault = "D:/v"\nffmpeg = "D:/tools/ffmpeg.exe"\n\n'
          '[gallery-dl]\ncookies = "firefox"\n\n' + X_SECTION + "\n" + IG_SECTION)


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, text: str, data: bytes | None = None) -> Path:
        path = self.tmp / "assmedia.toml"
        if data is not None:
            path.write_bytes(data)
        else:
            path.write_text(text, encoding="utf-8")
        return path


class LoadTests(ConfigTestCase):
    def test_reads_all_keys(self):
        cfg = load_config(self.write(SAMPLE))
        self.assertEqual((cfg.raw, cfg.state, cfg.vault, cfg.ffmpeg, cfg.cookies),
                         (Path("D:/m/raw"), Path("D:/m/state"), Path("D:/v"), Path("D:/tools/ffmpeg.exe"), "firefox"))
        self.assertEqual(cfg.x.own_accounts, frozenset({"me", "other"}))  # lowercased
        self.assertEqual(cfg.instagram.saved_account, "me")

    def test_platform_without_section(self):
        cfg = load_config(self.write(SAMPLE.replace(X_SECTION, "")))
        self.assertIsNone(cfg.x)
        self.assertIsNotNone(cfg.instagram)

    def test_platform_settings_optional(self):
        cfg = load_config(self.write(SAMPLE.replace(X_SECTION, "[x]\n").replace(IG_SECTION, "[instagram]\n")))
        self.assertEqual(cfg.x.own_accounts, frozenset())
        self.assertIsNone(cfg.instagram.saved_account)

    def test_missing_file(self):
        path = self.tmp / "nope.toml"
        with self.assertRaises(FileNotFoundError) as ctx:
            load_config(path)
        self.assertIn(str(path), str(ctx.exception))

    def test_bad_toml_names_file(self):
        path = self.write(SAMPLE.replace('raw = "D:/m/raw"', 'raw = "D:\\m\\raw"'))
        with self.assertRaises(ValueError) as ctx:
            load_config(path)
        self.assertIn(str(path), str(ctx.exception))

    def test_bom_is_accepted(self):
        path = self.write("", data=b"\xef\xbb\xbf" + SAMPLE.encode("utf-8"))
        self.assertEqual(load_config(path).raw, Path("D:/m/raw"))

    def test_utf16_names_file(self):
        with self.assertRaisesRegex(ValueError, "not UTF-8"):
            load_config(self.write("", data=SAMPLE.encode("utf-16")))

    def test_missing_or_relative_path(self):
        for key in ("raw", "state", "vault", "ffmpeg"):
            line = next(l for l in SAMPLE.splitlines() if l.startswith(f"{key} ="))
            with self.assertRaisesRegex(ValueError, rf"paths\.{key} is missing"):
                load_config(self.write(SAMPLE.replace(line + "\n", "")))
            with self.assertRaisesRegex(ValueError, rf"paths\.{key} must be an absolute path"):
                load_config(self.write(SAMPLE.replace(line, f'{key} = "relative/{key}"')))

    def test_cookies_required(self):
        with self.assertRaisesRegex(ValueError, r"gallery-dl\.cookies"):
            load_config(self.write(SAMPLE.replace('cookies = "firefox"', "")))

    def test_tables_must_be_tables(self):
        with self.assertRaisesRegex(ValueError, r"\[x\] must be a table"):
            load_config(self.write('x = "on"\n' + SAMPLE.replace(X_SECTION, "")))  # top level, before [paths]

    def test_own_must_be_a_list(self):
        with self.assertRaisesRegex(ValueError, r"x\.own"):
            load_config(self.write(SAMPLE.replace('own = ["Me", "other"]', 'own = "me"')))

    def test_saved_account_must_be_text(self):
        with self.assertRaisesRegex(ValueError, r"instagram\.saved"):
            load_config(self.write(SAMPLE.replace('saved = "me"', 'saved = ""')))


class DirsTests(ConfigTestCase):
    def test_dirs_split_raw_and_state(self):
        d = dirs(load_config(self.write(SAMPLE)), "x")
        self.assertEqual((d.items, d.threads, d.thumbs),
                         (Path("D:/m/raw/X/items"), Path("D:/m/raw/X/threads"), Path("D:/m/raw/X/thumbs")))
        self.assertEqual((d.crawl, d.tagging, d.build),
                         (Path("D:/m/state/X/_crawl"), Path("D:/m/state/X/tagging"), Path("D:/m/state/X/build")))

    def test_platform_folders(self):
        self.assertEqual(PLATFORMS, {"x": "X", "instagram": "Instagram"})
        self.assertEqual(dirs(load_config(self.write(SAMPLE)), "instagram").items, Path("D:/m/raw/Instagram/items"))


class ProblemTests(ConfigTestCase):
    def real(self, **over) -> str:
        vault = self.tmp / "vault"
        vault.mkdir(exist_ok=True)
        ffmpeg = self.tmp / "ffmpeg.exe"
        ffmpeg.write_bytes(b"")
        values = {"vault": vault.as_posix(), "ffmpeg": ffmpeg.as_posix()} | over
        return (SAMPLE.replace('vault = "D:/v"', f'vault = "{values["vault"]}"')
                .replace('ffmpeg = "D:/tools/ffmpeg.exe"', f'ffmpeg = "{values["ffmpeg"]}"'))

    def test_raw_and_state_need_not_exist(self):
        self.assertEqual(problems(load_config(self.write(self.real()))), [])

    def test_missing_vault_and_ffmpeg(self):
        cfg = load_config(self.write(self.real(vault="D:/nowhere/vault", ffmpeg="D:/nowhere/ffmpeg.exe")))
        found = problems(cfg)
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].startswith("paths.vault") and found[1].startswith("paths.ffmpeg"))



class OtherTests(unittest.TestCase):
    def test_split_config_arg(self):
        self.assertEqual(split_config_arg(["--config", "a.toml", "x", "pending"]), (Path("a.toml"), ["x", "pending"]))
        self.assertEqual(split_config_arg(["x", "pending"]), (None, ["x", "pending"]))
        with self.assertRaises(ValueError):
            split_config_arg(["--config"])

    def test_default_config_path(self):
        self.assertEqual(default_config_path(), ROOT / "assmedia.toml")

    def test_example_holds_no_instance_values(self):
        text = (ROOT / "assmedia.example.toml").read_text(encoding="utf-8")
        for word in ("V:/", "C:/Users", "FireSourcery", "firesourcery", "Vault0"):
            self.assertNotIn(word, text)
        cfg = load_config(ROOT / "assmedia.example.toml")
        self.assertIsNotNone(cfg.x)
        self.assertIsNotNone(cfg.instagram)


if __name__ == "__main__":
    unittest.main()
