"""The test package's guard: no test may write outside the system temp folder, so none can touch real data."""
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WriteGuardTests(unittest.TestCase):
    def setUp(self):
        self.file = ROOT / "guard-test-must-not-exist.txt"
        self.folder = ROOT / "guard-test-folder-must-not-exist"

    def tearDown(self):  # only matters while the guard is missing: then the writes below land
        if self.file.exists():
            os.remove(self.file)
        if self.folder.exists():
            os.rmdir(self.folder)

    def test_writing_a_file_outside_temp_fails(self):
        with self.assertRaises(PermissionError):
            self.file.write_text("x", encoding="utf-8")
        self.assertFalse(self.file.exists())

    def test_making_a_folder_outside_temp_fails(self):
        with self.assertRaises(PermissionError):
            self.folder.mkdir()
        self.assertFalse(self.folder.exists())

    def test_temp_and_reads_are_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sub").mkdir()
            (Path(tmp) / "sub" / "a.txt").write_text("ok", encoding="utf-8")
        self.assertIn("ASSMedia", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
