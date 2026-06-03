from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.build_catalog import build_bilingual_catalog


class BuildCatalogTest(unittest.TestCase):
    def test_build_from_fileparser_output_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "fileparser-output"
            output_dir.mkdir()
            (output_dir / "English.json").write_text('{"a":"Hello"}', encoding="utf-8")
            (output_dir / "ChineseTraditional.json").write_text('{"a":"你好"}', encoding="utf-8")
            output = root / "bilingual.json"
            merge_report = root / "merge-report.json"
            lint_report = root / "lint-report.json"

            result = build_bilingual_catalog(
                fileparser_output=output_dir,
                output=output,
                merge_report=merge_report,
                lint_report=lint_report,
            )
            catalog_data = json.loads(output.read_text(encoding="utf-8"))
            merge_report_exists = merge_report.exists()
            lint_report_exists = lint_report.exists()

        self.assertTrue(result.ok)
        self.assertEqual(result.english.endswith("English.json"), True)
        self.assertEqual(catalog_data["entries"][0]["text"], "Hello\n你好")
        self.assertTrue(merge_report_exists)
        self.assertTrue(lint_report_exists)

    def test_build_with_explicit_inputs_and_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            english = root / "en.json"
            chinese = root / "zh.json"
            terms = root / "terms.csv"
            output = root / "bilingual.json"
            english.write_text('{"a":"Connor"}', encoding="utf-8")
            chinese.write_text('{"a":"Connor"}', encoding="utf-8")
            terms.write_text("source,target\nConnor,CONNOR\n", encoding="utf-8")

            result = build_bilingual_catalog(english=english, chinese=chinese, terms=terms, output=output)
            catalog_data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(result.ok)
        self.assertEqual(catalog_data["entries"][0]["text"], "Connor\nCONNOR")
        self.assertEqual(result.merge["terminology"]["replacements"], 1)

    def test_build_requires_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_bilingual_catalog(output=Path(temp_dir) / "out.json")

        self.assertFalse(result.ok)
        self.assertIn("Pass --english and --chinese", result.errors[0])

    def test_build_reports_missing_discovered_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "fileparser-output"
            output_dir.mkdir()
            (output_dir / "English.json").write_text('{"a":"Hello"}', encoding="utf-8")

            result = build_bilingual_catalog(fileparser_output=output_dir, output=root / "bilingual.json")

        self.assertFalse(result.ok)
        self.assertIn("No Chinese catalog was selected.", result.errors)


if __name__ == "__main__":
    unittest.main()
