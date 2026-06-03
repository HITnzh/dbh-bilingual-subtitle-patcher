from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.patch_inject import patch_inject_workdir, save_patch_inject_result


class PatchInjectTest(unittest.TestCase):
    def test_patch_inject_auto_discovers_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))

            result = patch_inject_workdir(work)
            output = Path(result.output)
            report_path = Path(result.report_path)
            patched = json.loads(output.read_text(encoding="utf-8"))
            report_exists = report_path.exists()

        self.assertTrue(result.ok)
        self.assertEqual(patched["entries"][0]["text"], "Hello\n你好")
        self.assertTrue(report_exists)
        self.assertEqual(result.injection["report"]["updated"], 1)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.discovery["warnings"], [])

    def test_patch_inject_rejects_multiple_chinese_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "zh-Hans.json").write_text('{"a":"你好"}', encoding="utf-8")

            result = patch_inject_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Multiple Chinese" in error for error in result.errors))

    def test_patch_inject_accepts_explicit_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            extra = work / "extracted" / "zh-Hans.json"
            extra.write_text('{"a":"你好"}', encoding="utf-8")

            result = patch_inject_workdir(work, target=Path("ChineseTraditional.json"))
            patched = json.loads(Path(result.output).read_text(encoding="utf-8"))

        self.assertTrue(result.ok)
        self.assertEqual(patched["entries"][0]["text"], "Hello\n你好")

    def test_patch_inject_blocks_when_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "catalog" / "bilingual.json").unlink()

            result = patch_inject_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Bilingual catalog does not exist" in error for error in result.errors))

    def test_save_patch_inject_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            result = patch_inject_workdir(work)
            output = root / "result.json"

            save_patch_inject_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["injection"]["report"]["updated"], 1)


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text('{"a":"Hello\\n你好"}', encoding="utf-8")
    (work / "extracted" / "ChineseTraditional.json").write_text(
        '{"entries":[{"key":"a","text":"你好","speaker":"Connor"}]}',
        encoding="utf-8",
    )
    return work


if __name__ == "__main__":
    unittest.main()
