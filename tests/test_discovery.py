from pathlib import Path
import tempfile
import unittest

from dbh_bisub.discovery import discover_catalogs, infer_language_role


class DiscoveryTest(unittest.TestCase):
    def test_infer_language_role(self) -> None:
        self.assertEqual(infer_language_role("English.json"), "english")
        self.assertEqual(infer_language_role("localization/zh-Hans.json"), "chinese")
        self.assertEqual(infer_language_role("TraditionalChinese.json"), "chinese")
        self.assertEqual(infer_language_role("French.json"), "unknown")

    def test_discover_catalogs_recommends_english_and_chinese(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "English.json").write_text('{"a":"Hello"}', encoding="utf-8")
            (root / "ChineseTraditional.json").write_text('{"a":"你好"}', encoding="utf-8")

            report = discover_catalogs(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.recommended_english, "English.json")
        self.assertEqual(report.recommended_chinese, "ChineseTraditional.json")
        self.assertEqual(report.files[0].entry_count, 1)

    def test_discover_catalogs_warns_when_missing_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "French.json").write_text('{"a":"Bonjour"}', encoding="utf-8")

            report = discover_catalogs(root)

        self.assertTrue(report.ok)
        self.assertIn("No English catalog candidate was found.", report.warnings)
        self.assertIn("No Chinese catalog candidate was found.", report.warnings)

    def test_discover_catalogs_reports_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = discover_catalogs(Path(temp_dir) / "missing")

        self.assertFalse(report.ok)
        self.assertTrue(report.errors)


if __name__ == "__main__":
    unittest.main()
