from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.catalog import catalog_from_json
from dbh_bisub.inject_catalog import inject_catalog_data, inject_catalog_file


class InjectCatalogTest(unittest.TestCase):
    def test_injects_mapping_shape(self) -> None:
        source = catalog_from_json({"a": "Hello\n你好", "missing": "Unused"})
        target = {"a": "你好", "b": "保持"}

        patched, report = inject_catalog_data(source, target)

        self.assertEqual(patched, {"a": "Hello\n你好", "b": "保持"})
        self.assertTrue(report.ok)
        self.assertEqual(report.updated, 1)
        self.assertEqual(report.missing_in_target, ["missing"])
        self.assertEqual(report.missing_in_source, ["b"])

    def test_injects_entries_shape_preserving_metadata(self) -> None:
        source = catalog_from_json({"a": "Hello\n你好"})
        target = {"entries": [{"key": "a", "text": "你好", "speaker": "Connor"}]}

        patched, report = inject_catalog_data(source, target)

        self.assertEqual(patched["entries"][0]["text"], "Hello\n你好")
        self.assertEqual(patched["entries"][0]["speaker"], "Connor")
        self.assertEqual(report.updated, 1)

    def test_injects_value_field(self) -> None:
        source = catalog_from_json({"7": "World\n世界"})
        target = {"entries": [{"id": 7, "value": "世界"}]}

        patched, report = inject_catalog_data(source, target)

        self.assertEqual(patched["entries"][0]["value"], "World\n世界")
        self.assertEqual(report.updated, 1)

    def test_injects_nested_strings_shape(self) -> None:
        source = catalog_from_json({"a": "Hello\n你好"})
        target = {"language": "zh", "strings": {"a": "你好"}}

        patched, report = inject_catalog_data(source, target)

        self.assertEqual(patched["strings"]["a"], "Hello\n你好")
        self.assertEqual(patched["language"], "zh")
        self.assertEqual(report.target_entries, 1)

    def test_reports_missing_text_field(self) -> None:
        source = catalog_from_json({"a": "Hello"})
        target = {"entries": [{"key": "a", "speaker": "Connor"}]}

        patched, report = inject_catalog_data(source, target)

        self.assertEqual(patched, target)
        self.assertEqual(report.skipped, 1)
        self.assertEqual(report.issues[0].code, "missing_text")

    def test_inject_catalog_file_writes_output_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.json"
            target = root / "target.json"
            output = root / "patched.json"
            report_path = root / "report.json"
            source.write_text('{"a":"Hello\\n你好"}', encoding="utf-8")
            target.write_text('{"entries":[{"key":"a","text":"你好"}]}', encoding="utf-8")

            result = inject_catalog_file(source=source, target=target, output=output, report=report_path)
            patched_data = json.loads(output.read_text(encoding="utf-8"))
            report_data = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertTrue(result.report.ok)
        self.assertEqual(patched_data["entries"][0]["text"], "Hello\n你好")
        self.assertEqual(report_data["updated"], 1)


if __name__ == "__main__":
    unittest.main()
