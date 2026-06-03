from pathlib import Path
import tempfile
import unittest

from dbh_bisub.catalog import catalog_from_json
from dbh_bisub.terminology import TermRule, apply_terminology, apply_terminology_to_catalog, load_terminology


class TerminologyTest(unittest.TestCase):
    def test_load_terminology_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "terms.csv"
            path.write_text(
                "# comment\nsource,target,note\n康纳,康納,name\n仿生人,仿生人,term\n",
                encoding="utf-8",
            )

            rules = load_terminology(path)

        self.assertEqual([rule.source for rule in rules], ["康纳", "仿生人"])
        self.assertEqual(rules[0].target, "康納")
        self.assertEqual(rules[0].note, "name")

    def test_apply_terminology_longest_first(self) -> None:
        rules = [
            TermRule("仿生", "android"),
            TermRule("仿生人", "android person"),
        ]

        result = apply_terminology("仿生人和仿生", rules)

        self.assertEqual(result.text, "android person和android")
        self.assertEqual(result.replacements["仿生人"], 1)
        self.assertEqual(result.replacements["仿生"], 1)

    def test_apply_terminology_to_catalog(self) -> None:
        catalog = catalog_from_json({"a": "康纳是仿生人", "b": "没有命中"})
        rules = [TermRule("康纳", "康納"), TermRule("仿生人", "仿生人")]

        updated, report = apply_terminology_to_catalog(catalog, rules)

        self.assertEqual(updated.get_text("a"), "康納是仿生人")
        self.assertEqual(report.rules_loaded, 2)
        self.assertEqual(report.rules_matched, 2)
        self.assertEqual(report.replacements, 2)
        self.assertEqual(report.by_source["康纳"], 1)


if __name__ == "__main__":
    unittest.main()
