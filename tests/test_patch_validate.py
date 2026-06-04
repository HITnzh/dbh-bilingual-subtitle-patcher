from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.patch_validate import save_patch_validation_result, validate_patch_workdir


class PatchValidateTest(unittest.TestCase):
    def test_validate_ready_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))

            result = validate_patch_workdir(work)

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertTrue(any(check.id == "target_catalog" and check.status == "ok" for check in result.checks))
        self.assertTrue(any(check.id == "file_size_table" and check.status == "ok" for check in result.checks))

    def test_validate_blocks_multiple_chinese_candidates_without_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "zh-Hans.json").write_text('{"a":"你好"}', encoding="utf-8")

            result = validate_patch_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Multiple Chinese" in error for error in result.errors))

    def test_validate_accepts_explicit_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "zh-Hans.json").write_text('{"a":"你好"}', encoding="utf-8")

            result = validate_patch_workdir(work, target=Path("ChineseTraditional.json"))

        self.assertTrue(result.ok)
        self.assertTrue(any(check.id == "target_catalog" and check.details["entries"] == 1 for check in result.checks))

    def test_validate_accepts_idx_text_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_text_workdir(Path(temp_dir))

            result = validate_patch_workdir(work)

        self.assertTrue(result.ok)
        self.assertTrue(any(check.id == "target_catalog" and check.details["text_files"] == 1 for check in result.checks))

    def test_validate_blocks_missing_file_size_table_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "BigFile_PC.FileSizeTable").unlink()

            result = validate_patch_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("FileSizeTable" in error for error in result.errors))

    def test_validate_can_warn_for_missing_file_size_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "BigFile_PC.FileSizeTable").unlink()

            result = validate_patch_workdir(work, allow_missing_file_size_table=True)

        self.assertTrue(result.ok)
        self.assertTrue(any("FileSizeTable" in warning for warning in result.warnings))

    def test_validate_blocks_missing_staged_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "catalog" / "bilingual.json").unlink()

            result = validate_patch_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("bilingual catalog does not exist" in error for error in result.errors))

    def test_save_patch_validation_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            result = validate_patch_workdir(work)
            output = root / "validation.json"

            save_patch_validation_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))
            work_text = str(work)

        self.assertTrue(data["ok"])
        self.assertEqual(data["work_dir"], work_text)


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text('{"a":"Hello\\n你好"}', encoding="utf-8")
    (work / "extracted" / "ChineseTraditional.json").write_text(
        '{"entries":[{"key":"a","text":"你好"}]}',
        encoding="utf-8",
    )
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


def _make_text_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted" / "BigFile_PC_exp").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text('{"a":"Hello\\nNi hao"}', encoding="utf-8")
    (work / "extracted" / "BigFile_PC_exp" / "0x00000000.txt").write_text("a=Old\r\n", encoding="utf-8")
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


if __name__ == "__main__":
    unittest.main()
