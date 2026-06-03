from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.catalog import catalog_from_json, load_catalog, merge_catalogs, save_catalog, save_report


class CatalogTest(unittest.TestCase):
    def test_loads_mapping_shape(self) -> None:
        catalog = catalog_from_json({"a": "Hello", "b": {"text": "World", "speaker": "Connor"}})

        self.assertEqual(catalog.count, 2)
        self.assertEqual(catalog.get_text("a"), "Hello")
        self.assertEqual(catalog.entries["b"].metadata, {"speaker": "Connor"})

    def test_loads_entries_shape(self) -> None:
        catalog = catalog_from_json({"entries": [{"key": "a", "text": "Hello"}, {"id": 7, "value": "World"}]})

        self.assertEqual(catalog.keys(), ["a", "7"])
        self.assertEqual(catalog.get_text("7"), "World")

    def test_merges_catalogs_with_warnings(self) -> None:
        english = catalog_from_json({"a": "{PLAYER} Hello", "b": "Only English"})
        chinese = catalog_from_json({"a": "你好", "c": "只有中文"})

        result = merge_catalogs(english, chinese)

        self.assertEqual(result.catalog.get_text("a"), "{PLAYER} Hello\n你好")
        self.assertEqual(result.catalog.get_text("b"), "Only English")
        self.assertEqual(result.catalog.get_text("c"), "只有中文")
        self.assertEqual(result.report.missing_chinese, 1)
        self.assertEqual(result.report.missing_english, 1)
        self.assertEqual(result.report.token_warnings, 1)
        self.assertEqual(len(result.report.issues), 3)

    def test_save_and_load_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "catalog.json"
            catalog = catalog_from_json({"a": "Hello"})

            save_catalog(output, catalog)
            loaded = load_catalog(output)

        self.assertEqual(loaded.get_text("a"), "Hello")

    def test_save_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            english = catalog_from_json({"a": "Hello"})
            chinese = catalog_from_json({"a": "你好"})
            report_path = Path(temp_dir) / "report.json"

            result = merge_catalogs(english, chinese)
            save_report(report_path, result.report)
            data = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["merged"], 1)


if __name__ == "__main__":
    unittest.main()
