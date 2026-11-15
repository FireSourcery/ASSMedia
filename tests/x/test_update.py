"""The update command: the bookmarks pass, pending, the lookup pass, pending again (plan Task 5)."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from tests.x.fixtures import author, write_tweet
from tests.x.test_cli import CliTestCase
from assmedia.x.update import BOOKMARKS_URL, bookmark_args, cmd_update, has_lookups, lookup_args

CONF, CRAWL = Path("D:/m/X/gallery-dl.conf"), Path("D:/m/X/_crawl")
ME = author(1, "some_artist", "Some Artist")


class ArgsTests(unittest.TestCase):
    def test_bookmark_args(self):
        self.assertEqual(bookmark_args(CONF, full=False),
                         ["-c", "D:/m/X/gallery-dl.conf", "--abort", "5", "https://x.com/i/bookmarks"])
        self.assertEqual(bookmark_args(CONF, full=True), ["-c", "D:/m/X/gallery-dl.conf", "https://x.com/i/bookmarks"])

    def test_lookup_args(self):
        self.assertEqual(lookup_args(CONF, CRAWL, CRAWL / "threads-pending.txt"), [
            "-c", "D:/m/X/gallery-dl.conf",
            "-o", 'output.logfile={"path": "D:/m/X/_crawl/threads.log", "mode": "a", "level": "info"}',
            "-o", "output.errorfile=D:/m/X/_crawl/threads-failed.txt",
            "-I", "D:/m/X/_crawl/threads-pending.txt"])

    def test_has_lookups(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.txt"
            self.assertFalse(has_lookups(path))
            path.write_text('# -post-filter = "x"\n# https://x.com/a/status/1\n', encoding="utf-8")
            self.assertFalse(has_lookups(path))
            path.write_text('-post-filter = "x"\nhttps://x.com/a/status/2\n', encoding="utf-8")
            self.assertTrue(has_lookups(path))


class UpdateTests(CliTestCase):
    def update(self, **kwargs):
        """Run cmd_update with a fake gallery-dl; returns (exit code, the args of each run, printed text)."""
        calls = []
        result = kwargs.pop("result", 0)

        def run(args):
            calls.append(args)
            if isinstance(result, Exception):
                raise result
            return result

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_update(self.xp, run=run, **kwargs)
        return code, calls, out.getvalue()

    def test_both_passes_with_pending_between(self):
        write_tweet(self.xp.core.items, "60", author=ME, reply_count=3)  # needs a lookup
        code, calls, _ = self.update()
        self.assertEqual(code, 0)
        self.assertEqual([c[-1] for c in calls], [BOOKMARKS_URL, (self.xp.crawl / "threads-pending.txt").as_posix()])
        self.assertIn("/status/60", (self.xp.crawl / "threads-pending.txt").read_text(encoding="utf-8"))

    def test_nothing_queued_skips_lookup_pass(self):
        write_tweet(self.xp.core.items, "61", author=ME)
        code, calls, out = self.update()
        self.assertEqual(len(calls), 1)
        self.assertIn("lookup pass: nothing queued", out)

    def test_lookups_option_runs_only_that_list(self):
        retry = self.xp.crawl / "threads-retry-1.txt"
        retry.write_text("https://x.com/a/status/62\n", encoding="utf-8")
        code, calls, _ = self.update(lookups=retry)
        self.assertEqual([c[-1] for c in calls], [retry.as_posix()])

    def test_lookups_option_missing_file_refused(self):
        code, calls, out = self.update(lookups=self.xp.crawl / "threads-retyr-1.txt")
        self.assertEqual((code, calls), (2, []))
        self.assertIn("no lookup list at", out)

    def test_lookups_option_refuses_live_failed_list(self):
        failed = self.xp.crawl / "threads-failed.txt"
        failed.write_text("https://x.com/a/status/64\n", encoding="utf-8")
        code, calls, out = self.update(lookups=failed)
        self.assertEqual((code, calls), (2, []))
        self.assertIn("rename it first", out)

    def test_failed_count_leaves_out_skipped(self):
        (self.xp.crawl / "threads-failed.txt").write_text(
            "https://x.com/a/status/70\nhttps://x.com/a/status/71\n", encoding="utf-8")
        (self.xp.crawl / "threads-skip.txt").write_text("70\n", encoding="utf-8")
        code, calls, out = self.update()
        self.assertIn("failed lookups 1 (see", out)

    def test_nonzero_exit_keeps_going(self):
        write_tweet(self.xp.core.items, "63", author=ME, reply_count=1)
        code, calls, _ = self.update(result=1)
        self.assertEqual((code, len(calls)), (0, 2))

    def test_gallery_dl_missing_stops(self):
        code, calls, _ = self.update(result=OSError("not found"))
        self.assertEqual((code, len(calls)), (2, 1))


class FilledConfTests(unittest.TestCase):
    """`update` writes <state>/X/_crawl/gallery-dl.conf from the config before gallery-dl runs."""

    def test_update_writes_the_filled_conf_first(self):
        import json
        import tempfile
        from unittest import mock

        from assmedia.x.cli import main
        from tests.core.fixtures import config_with
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).as_posix()
            cfg = config_with(raw=f"{root}/raw", state=f"{root}/state", cookies="edge")
            seen = {}

            def fake(xp, **kw):
                seen["conf"] = json.loads(xp.gallery_conf.read_text(encoding="utf-8"))
                return 0

            with mock.patch("assmedia.x.update.cmd_update", side_effect=fake):
                self.assertEqual(main(["update"], config=cfg), 0)
        conf = seen["conf"]
        self.assertEqual(conf["extractor"]["base-directory"], f"{root}/raw/X/items/")
        self.assertEqual(conf["extractor"]["twitter"]["cookies"], ["edge"])
        self.assertEqual(conf["extractor"]["twitter"]["filename"], "{tweet_id}_{num:>02}.{extension}")


if __name__ == "__main__":
    unittest.main()
