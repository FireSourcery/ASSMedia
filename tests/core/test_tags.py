import json
import tempfile
import unittest
from pathlib import Path

from assmedia.core.tags import canonical_domains, canonicalize, hub_names, load_tags, validate_name


class ValidateNameTests(unittest.TestCase):
    def test_validate_rejects_pipe(self):
        with self.assertRaisesRegex(ValueError, r"\|"):
            validate_name("Sandra | Art")

    def test_validate_rejects_empty(self):
        with self.assertRaises(ValueError):
            validate_name("  ")

    def test_validate_accepts_plain_name(self):
        validate_name("Miss Fortune")


class CanonicalizeTests(unittest.TestCase):
    def test_canonicalize_alias(self):
        index = {"thelaurenchen": "Lauren Chen", "lauren chen": "Lauren Chen"}
        self.assertEqual(canonicalize("thelaurenchen", index), "Lauren Chen")
        self.assertEqual(canonicalize("Foo", index), "Foo")

    def test_canonicalize_strips_spaces(self):
        self.assertEqual(canonicalize(" Foo ", {}), "Foo")


class LoadTagsTests(unittest.TestCase):
    def write(self, data):
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "tags.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)
        return path

    def test_load_tags_fields(self):
        tags = load_tags(self.write({"X": {
            "title": "T", "description": "D", "people": ["A"], "subjects": ["B"],
            "themes": [], "creator_person": "A", "domain": ["Coding"]}}))
        t = tags["X"]
        self.assertEqual((t.title, t.description, t.people, t.subjects, t.themes),
                         ("T", "D", ["A"], ["B"], []))
        self.assertEqual((t.creator_person, t.domain), ("A", ["Coding"]))

    def test_load_tags_defaults_missing_fields(self):
        t = load_tags(self.write({"X": {"title": "T"}}))["X"]
        self.assertEqual((t.people, t.creator_person, t.domain), ([], None, []))

    def test_load_tags_rejects_string_for_list(self):
        with self.assertRaisesRegex(ValueError, "X: subjects"):
            load_tags(self.write({"X": {"subjects": "Sideshow"}}))

    def test_load_tags_rejects_list_for_creator(self):
        with self.assertRaisesRegex(ValueError, "X: creator_person"):
            load_tags(self.write({"X": {"creator_person": ["Someone"]}}))

    def test_load_tags_rejects_non_string_title(self):
        with self.assertRaisesRegex(ValueError, "X: title"):
            load_tags(self.write({"X": {"title": 5}}))

    def test_load_tags_rejects_non_string_list_item(self):
        with self.assertRaisesRegex(ValueError, "X: people"):
            load_tags(self.write({"X": {"people": ["A", 3]}}))

    def test_load_tags_rejects_unknown_field(self):
        with self.assertRaisesRegex(ValueError, "coding"):
            load_tags(self.write({"X": {"coding": True}}))


class DomainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.domains = Path(self._tmp.name)
        for hub in ("AI", "Coding"):
            (self.domains / f"{hub}.md").write_text("", encoding="utf-8")

    def test_canonical_domains_case_insensitive(self):
        self.assertEqual(canonical_domains(["coding", "AI", "Coding"], hub_names(self.domains)),
                         ["Coding", "AI"])

    def test_canonical_domains_rejects_unknown(self):
        with self.assertRaisesRegex(ValueError, "Cooking"):
            canonical_domains(["Cooking"], hub_names(self.domains))


if __name__ == "__main__":
    unittest.main()
