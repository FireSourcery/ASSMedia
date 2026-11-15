"""fsread: read texts and list folders 16 at a time, results in the order given."""
import tempfile
import unittest
from pathlib import Path

from assmedia.core import fsread


class FsreadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_texts_in_given_order(self):
        paths = [self.write(f"{i:02}.txt", f"text {i}") for i in range(40)]
        self.assertEqual(fsread.read_texts(paths, workers=4), [f"text {i}" for i in range(40)])

    def test_universal_newlines_like_read_text(self):
        path = self.root / "crlf.md"
        path.write_bytes(b"a\r\nb")
        self.assertEqual(fsread.read_texts([path]), [path.read_text(encoding="utf-8")])

    def test_errors_in_place(self):
        good, missing, bad = self.write("g.txt", "ok"), self.root / "missing.txt", self.root / "bad.txt"
        bad.write_bytes(b"\xff\xfe\xfa")
        out = fsread.read_texts([good, missing, bad])
        self.assertEqual(out[0], "ok")
        self.assertIsInstance(out[1], FileNotFoundError)
        self.assertIsInstance(out[2], UnicodeDecodeError)

    def test_read_all_raises_first_error_in_order(self):
        bad = self.root / "bad.txt"
        bad.write_bytes(b"\xff")
        with self.assertRaises(FileNotFoundError):
            fsread.read_all([self.write("g.txt", "ok"), self.root / "missing.txt", bad])

    def test_list_files_regular_files_sorted(self):
        folder = self.root / "f"
        (folder / "sub").mkdir(parents=True)
        for name in ("b.jpg", "a.json"):
            (folder / name).write_bytes(b"")
        out = fsread.list_files([folder, self.root / "missing"])
        self.assertEqual(out[0], ["a.json", "b.jpg"])
        self.assertIsInstance(out[1], FileNotFoundError)

    def test_empty_input(self):
        self.assertEqual((fsread.read_texts([]), fsread.read_all([]), fsread.list_files([])), ([], [], []))


if __name__ == "__main__":
    unittest.main()
