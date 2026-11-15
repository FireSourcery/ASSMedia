"""`update`: the Saved-feed download, then `pending`'s summary, in one command."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from assmedia.instagram import cli
from tests.core.fixtures import config_with
from assmedia.instagram.update import cmd_update, download_args
from tests.core.fixtures import make_paths, make_post_folder

CONF = Path("D:/R/_tools/gallery-dl.conf")


class ArgsTests(unittest.TestCase):
    def test_download_args(self):
        self.assertEqual(download_args(CONF, "me", False),
                         ["-c", str(CONF), "--abort", "5", "https://www.instagram.com/me/saved/"])
        self.assertEqual(download_args(CONF, "me", True), ["-c", str(CONF), "https://www.instagram.com/me/saved/"])


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.p = make_paths(Path(self._tmp.name))
        self.p.items.mkdir()
        make_post_folder(self.p.items, "NEW", ["NEW_01.mp4"])
        make_post_folder(self.p.items, "HALF", ["HALF_01.mp4"], {"count": 2})  # one file still missing

    def update(self, account, run, full=False):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cmd_update(self.p, account, full=full, run=run, conf=CONF)
        return code, out.getvalue()

    def test_update_runs_then_reports(self):
        calls = []

        def run(args):
            calls.append(args)
            return 1  # one failed file is enough for a non-zero exit

        code, out = self.update("me", run)
        todo, incomplete = cli.pending(self.p)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [download_args(CONF, "me", False)])
        self.assertIn("download: exit 1", out)
        self.assertIn(f"done: new {len(todo)}, incomplete {len(incomplete)}", out)

    def test_update_on_a_new_instance(self):
        """A first download that saves nothing (a failed login, say) leaves no items\\: the summary still prints."""
        self.p = make_paths(Path(self._tmp.name) / "new")
        code, out = self.update("me", lambda args: 1)
        self.assertEqual(code, 0)
        self.assertIn("done: new 0, incomplete 0", out)

    def test_update_full_drops_the_stop(self):
        calls = []
        self.update("me", lambda args: calls.append(args) or 0, full=True)
        self.assertNotIn("--abort", calls[0])

    def test_update_needs_account(self):
        calls = []
        code, out = self.update(None, lambda args: calls.append(args) or 0)
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertIn("[instagram] saved", out)
        self.assertIn("assmedia.toml", out)

    def test_update_gallery_dl_missing(self):
        def run(args):
            raise OSError("no python")

        code, out = self.update("me", run)
        self.assertEqual(code, 2)
        self.assertIn("gallery-dl could not be started", out)


class CliWiringTests(unittest.TestCase):
    def test_cli_update_wired(self):
        """main writes the filled-in config, so every path here is a temporary folder."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = config_with(raw=(root / "raw").as_posix(), state=(root / "state").as_posix())
            out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")  # main reconfigures stdout, so not a StringIO
            with mock.patch("assmedia.instagram.update.cmd_update", return_value=0) as fake, redirect_stdout(out):
                self.assertEqual(cli.main(["update", "--full"], config=cfg), 0)
            p, account = fake.call_args.args
            self.assertEqual(account, "me")
            self.assertTrue(fake.call_args.kwargs["full"])
            self.assertEqual(fake.call_args.kwargs["conf"], root / "state" / "Instagram" / "_crawl" / "gallery-dl.conf")
            self.assertEqual(p.items, root / "raw" / "Instagram" / "items")


class FilledConfTests(unittest.TestCase):
    """`update` writes <state>/Instagram/_crawl/gallery-dl.conf from the config before gallery-dl runs."""

    def test_update_writes_the_filled_conf_first(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).as_posix()
            cfg = config_with(raw=f"{root}/raw", state=f"{root}/state", cookies="edge")
            seen = {}

            def fake(p, account, **kw):
                seen["conf"] = json.loads(kw["conf"].read_text(encoding="utf-8"))
                return 0

            out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
            with mock.patch("assmedia.instagram.update.cmd_update", side_effect=fake), redirect_stdout(out):
                self.assertEqual(cli.main(["update"], config=cfg), 0)
        conf = seen["conf"]
        self.assertEqual(conf["extractor"]["base-directory"], f"{root}/raw/Instagram/items/")
        self.assertEqual(conf["extractor"]["instagram"]["cookies"], ["edge"])
        self.assertEqual(conf["output"]["errorfile"], f"{root}/state/Instagram/_crawl/failed-urls.txt")


if __name__ == "__main__":
    unittest.main()
