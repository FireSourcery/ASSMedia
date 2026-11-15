"""Names a concepts plan proposed that got no page by choice (plan Task 4)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from assmedia.x.declined import filter_plan, record_declined, seed_declined


def entry(name, count):
    return {"name": name, "count": count, "fields": ["subjects"], "suggested_kind": None, "saves": []}


class DeclinedTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def batch(self, name, new, applied=None, mtime=None):
        """A batch's plan, and its concepts file unless `applied` is None."""
        plan = self.dir / f"{name}.plan.json"
        plan.write_text(json.dumps({"new": new}), encoding="utf-8")
        if applied is not None:
            (self.dir / f"{name}.json").write_text(json.dumps({n: {} for n in applied}), encoding="utf-8")
        if mtime is not None:
            os.utime(plan, (mtime, mtime))

    def test_left_out_names_are_recorded(self):
        declined = {}
        added = record_declined(declined, {"new": [entry("Russia", 2), entry("Pat", 3)]}, {"Pat"}, "b1")
        self.assertEqual((added, declined), (["Russia"], {"Russia": {"count": 2, "batch": "b1"}}))

    def test_applied_match_ignores_case(self):
        declined = {}
        record_declined(declined, {"new": [entry("Pat", 3)]}, {"pat"}, "b1")
        self.assertEqual(declined, {})

    def test_declined_name_leaves_new(self):
        out = filter_plan({"new": [entry("Russia", 2), entry("Pat", 3)], "conflicts": []},
                          {"russia": {"count": 2, "batch": "b1"}})
        self.assertEqual([e["name"] for e in out["new"]], ["Pat"])
        self.assertEqual([e["name"] for e in out["declined"]], ["Russia"])
        self.assertEqual(out["conflicts"], [])

    def test_grown_count_returns_to_new(self):
        out = filter_plan({"new": [entry("Russia", 3)]}, {"Russia": {"count": 2, "batch": "b1"}})
        self.assertEqual(([e["name"] for e in out["new"]], out["declined"]), (["Russia"], []))

    def test_seed_skips_unapplied_batches_and_existing_pages(self):
        self.batch("b1", [entry("Russia", 2), entry("Pat", 3), entry("Yiwu", 2)], applied=["Pat"])
        self.batch("b2", [entry("Kazakhstan", 2)])
        seeded = seed_declined(self.dir, has_page=lambda n: n.lower() == "yiwu")
        self.assertEqual(seeded, {"Russia": {"count": 2, "batch": "b1"}})

    def test_seed_later_batch_wins(self):
        self.batch("b2", [entry("Russia", 2)], applied=[], mtime=2_000_000_000)
        self.batch("b1", [entry("Russia", 2)], applied=[], mtime=1_000_000_000)
        self.assertEqual(seed_declined(self.dir, has_page=lambda n: False)["Russia"]["batch"], "b2")


if __name__ == "__main__":
    unittest.main()
