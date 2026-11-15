import json
import tempfile
import unittest
from pathlib import Path

from assmedia.x.tags import XTags, load_x_tags


class LoadXTagsTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_x_tags(path)

    def test_loads_all_fields(self):
        tags = self.load({"123": {"title": "T", "description": "D", "people": ["A"], "subjects": ["S"],
                                  "themes": ["M"], "creator_person": "C", "quoted_person": "Q",
                                  "source_person": None, "domain": ["AI"]}})
        self.assertEqual(tags["123"], XTags(title="T", description="D", people=["A"], subjects=["S"], themes=["M"],
                                            creator_person="C", domain=["AI"], quoted_person="Q",
                                            source_person=None))

    def test_load_x_tags_rejects_unknown_and_bad_types(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            self.load({"1": {"title": "T", "creator": "X"}})
        with self.assertRaisesRegex(ValueError, "quoted_person"):
            self.load({"1": {"quoted_person": 5}})
        with self.assertRaisesRegex(ValueError, "people"):
            self.load({"1": {"people": "A"}})


if __name__ == "__main__":
    unittest.main()
