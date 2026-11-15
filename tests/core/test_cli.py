"""assmedia.py: one entry point for every platform."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from assmedia.cli import main


class EntryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.ffmpeg = self.root / "ffmpeg.exe"
        self.ffmpeg.write_bytes(b"")

    def toml(self, *, vault: str | None = None, without: str | None = None) -> str:
        sections = {"x": '[x]\nown = ["me"]\n', "instagram": '[instagram]\nsaved = "me"\n'}
        text = (f'[paths]\nraw = "{(self.root / "raw").as_posix()}"\nstate = "{(self.root / "state").as_posix()}"\n'
                f'vault = "{vault or self.vault.as_posix()}"\nffmpeg = "{self.ffmpeg.as_posix()}"\n\n'
                '[gallery-dl]\ncookies = "firefox"\n\n'
                + "".join(body for name, body in sections.items() if name != without))
        path = self.root / "assmedia.toml"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_main(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_unconfigured_platform_stops(self):
        code, _, err = self.run_main(["--config", self.toml(without="x"), "x", "pending"])
        self.assertEqual(code, 2)
        self.assertIn("[x] isn't set up", err)

    def test_x_works_without_instagram_section(self):
        code, out, err = self.run_main(["--config", self.toml(without="instagram"), "x", "pending"])
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.strip(), "new 0, ready 0, waiting_lookup 0, added_to_list 0, incomplete 0")

    def test_config_problem_is_one_line(self):
        code, _, err = self.run_main(["--config", self.toml(vault="D:/nowhere/vault"), "x", "pending"])
        self.assertEqual((code, err.count("\n")), (2, 1))
        self.assertTrue(err.startswith("assmedia: paths.vault"), err)

    def test_missing_config_is_one_line(self):
        code, _, err = self.run_main(["--config", str(self.root / "none.toml"), "x", "pending"])
        self.assertEqual((code, err.count("\n")), (2, 1))

    def test_pending_on_empty_instance(self):
        code, out, _ = self.run_main(["--config", self.toml(), "x", "pending"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "new 0, ready 0, waiting_lookup 0, added_to_list 0, incomplete 0")

    def test_relink_needs_no_config(self):
        pages = self.root / "pages"
        pages.mkdir()
        (pages / "A.md").write_text("![](file:///D:/old/thumbs/1.jpg)\n", encoding="utf-8")
        code, out, _ = self.run_main(["--config", str(self.root / "none.toml"), "relink", str(pages), "D:/old", "D:/new", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("would change 1 links in 1 pages", out)

    def test_unknown_platform_shows_usage(self):
        code, _, err = self.run_main(["tiktok", "pending"])
        self.assertEqual(code, 2)
        self.assertIn("x|instagram|relink", err)


if __name__ == "__main__":
    unittest.main()
