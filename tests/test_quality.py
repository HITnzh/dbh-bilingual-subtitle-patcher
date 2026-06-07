import unittest

from dbh_bisub.catalog import catalog_from_json
from dbh_bisub.quality import inspect_catalog_quality


class QualityTest(unittest.TestCase):
    def test_clean_catalog(self) -> None:
        catalog = catalog_from_json({"a": "Hello{B}你好"})

        report = inspect_catalog_quality(catalog)

        self.assertTrue(report.ok)
        self.assertEqual(report.issue_count, 0)
        self.assertEqual(report.longest_line_chars, 5)

    def test_warns_on_empty_text(self) -> None:
        catalog = catalog_from_json({"a": ""})

        report = inspect_catalog_quality(catalog)

        self.assertEqual(report.issues[0].code, "empty_text")

    def test_warns_on_line_and_total_limits(self) -> None:
        catalog = catalog_from_json({"a": "abcdef\n123456\nxyz"})

        report = inspect_catalog_quality(catalog, max_lines=2, max_line_chars=4, max_total_chars=10)

        self.assertEqual(report.issues_by_code["too_many_lines"], 1)
        self.assertEqual(report.issues_by_code["line_too_long"], 1)
        self.assertEqual(report.issues_by_code["text_too_long"], 1)

    def test_warns_when_control_tokens_differ_between_lines(self) -> None:
        catalog = catalog_from_json({"a": "{PLAYER} Hello\n你好"})

        report = inspect_catalog_quality(catalog)

        self.assertEqual(report.issues_by_code["control_tokens_differ"], 1)

    def test_ignores_timed_cue_tokens_between_visual_lines(self) -> None:
        catalog = catalog_from_json({"a": "{*1}Hello{B}Ni hao"})

        report = inspect_catalog_quality(catalog)

        self.assertNotIn("control_tokens_differ", report.issues_by_code)


if __name__ == "__main__":
    unittest.main()
