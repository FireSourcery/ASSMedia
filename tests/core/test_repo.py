"""The repo tracks the tool, its tests and docs, and never an instance's data."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTANCE_DIRS = ("raw", "state", "logs")


def git_ls_files(root: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise unittest.SkipTest("git isn't on PATH")
    done = subprocess.run([git, "-C", str(root), "ls-files"], capture_output=True, text=True)
    if done.returncode != 0:
        raise unittest.SkipTest(f"{root} isn't a git repo")
    return done.stdout.splitlines()


class RepoTests(unittest.TestCase):
    def test_repo_tracks_no_instance_data(self):
        files = git_ls_files(ROOT)
        bad = [f for f in files if f.split("/")[0] in INSTANCE_DIRS or f == "assmedia.toml"]
        self.assertEqual(bad, [])

    def test_gitignore_covers_instance_data(self):
        rules = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
        for rule in ("raw/", "state/", "logs/", "assmedia.toml"):
            self.assertIn(rule, rules)


if __name__ == "__main__":
    unittest.main()
