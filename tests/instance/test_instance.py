"""Checks of this instance's own config and files. Skipped where there's no assmedia.toml (a fresh clone)."""
import re
import unittest

from assmedia.core.config import default_config_path, dirs, load_config, problems
from assmedia.core.gallerydl import fill

CONFIG = default_config_path()


def path_values(node) -> list[str]:
    if isinstance(node, dict):
        return [v for value in node.values() for v in path_values(value)]
    if isinstance(node, list):
        return [v for value in node for v in path_values(value)]
    return [node] if isinstance(node, str) and re.match(r"[A-Za-z]:/", node) else []


@unittest.skipUnless(CONFIG.is_file(), "no assmedia.toml: a fresh clone")
class InstanceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config(CONFIG)

    def test_config_has_no_problems(self):
        self.assertEqual(problems(self.cfg, "x"), [])

    def test_filled_confs_under_raw_or_state(self):
        import json
        from assmedia.instagram import update as ig
        from assmedia.x import update as x
        roots = (self.cfg.raw.as_posix().rstrip("/") + "/", self.cfg.state.as_posix().rstrip("/") + "/")
        for platform, module in (("x", x), ("instagram", ig)):
            if getattr(self.cfg, platform) is None:
                continue
            conf = fill(json.loads(module.TEMPLATE.read_text(encoding="utf-8")), module.conf_values(self.cfg))
            self.assertEqual([p for p in path_values(conf) if not p.startswith(roots)], [], platform)

    def test_thread_test_list_has_stop_lines(self):
        """The five tweets the thread lookups were tested on: each URL comes after its own stop line."""
        listing = dirs(self.cfg, "x").crawl / "threads-test.txt"
        if not listing.is_file():
            self.skipTest("no threads-test.txt in this instance")
        ids = ["2120094207604035595", "2120206372478566799", "2120206365759094857", "1932695486684950962",
               "2119430401701621865"]
        rows = [row.removeprefix("# ") for row in listing.read_text(encoding="utf-8").splitlines()]
        rows = [row for row in rows if row.startswith(("-post-filter", "https://"))]
        self.assertEqual(len(rows), 2 * len(ids))
        import json
        for (option, url), tweet_id in zip(zip(rows[::2], rows[1::2]), ids):
            key, _, value = option.partition("=")
            self.assertEqual(key.strip(), "-post-filter")
            self.assertEqual(json.loads(value.strip()),
                             f"author['id'] == user['id'] or tweet_id < {tweet_id} or abort()")
            self.assertTrue(url.startswith("https://x.com/") and url.endswith(f"/status/{tweet_id}"), url)


if __name__ == "__main__":
    unittest.main()
