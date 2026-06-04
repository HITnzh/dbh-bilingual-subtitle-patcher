from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.patch_stage import save_patch_stage_result, stage_patch_workdir


class PatchStageTest(unittest.TestCase):
    def test_stage_runs_inject_package_and_repack_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = stage_patch_workdir(
                game_dir,
                work,
                idx_detroit=tool,
                require_repack_plan=True,
            )
            generated = json.loads((work / "generated" / "ChineseTraditional.json").read_text(encoding="utf-8"))
            package_manifest_exists = (work / "reports" / "package-manifest.json").exists()

        self.assertTrue(result.ok)
        self.assertEqual(result.injection["injection"]["report"]["updated"], 1)
        self.assertEqual(result.package["files"][0]["relative_path"], "ChineseTraditional.json")
        self.assertTrue(result.package["repack_plan"]["ok"])
        self.assertTrue(package_manifest_exists)
        self.assertEqual(generated["entries"][0]["text"], "Hello\n你好")
        self.assertTrue(any(step.id == "repack_preflight" and step.status == "ready" for step in result.steps))

    def test_stage_blocks_before_mutating_when_backup_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)

            result = stage_patch_workdir(root / "missing-game", work)
            generated_exists = (work / "generated" / "ChineseTraditional.json").exists()

        self.assertFalse(result.ok)
        self.assertIsNone(result.injection)
        self.assertIsNone(result.package)
        self.assertFalse(generated_exists)
        self.assertTrue(any("Backup preflight failed" in error for error in result.errors))

    def test_stage_supports_idx_text_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_text_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = stage_patch_workdir(
                game_dir,
                work,
                idx_detroit=tool,
                require_repack_plan=True,
            )
            generated = (work / "generated" / "BigFile_PC_exp" / "0x00000000.txt").read_text(encoding="utf-8")

        self.assertTrue(result.ok)
        self.assertEqual(result.injection["injection"]["mode"], "idx_text")
        self.assertIn("a=Hello[n]Ni hao", generated)
        self.assertTrue(result.package["repack_plan"]["ok"])
        self.assertTrue(any(step.id == "repack_preflight" and step.status == "ready" for step in result.steps))

    def test_stage_blocks_when_injection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            (work / "catalog" / "bilingual.json").unlink()

            result = stage_patch_workdir(game_dir, work)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.injection)
        self.assertIsNone(result.package)
        self.assertTrue(any("Catalog injection failed" in error for error in result.errors))

    def test_stage_allows_missing_repack_plan_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            (work / "extracted" / "BigFile_PC.FileSizeTable").unlink()

            result = stage_patch_workdir(game_dir, work)

        self.assertTrue(result.ok)
        self.assertIsNone(result.package["repack_plan"])
        self.assertTrue(any("FileSizeTable" in warning for warning in result.warnings))
        self.assertTrue(any(step.id == "repack_preflight" and step.status == "pending" for step in result.steps))

    def test_stage_can_require_repack_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            (work / "extracted" / "BigFile_PC.FileSizeTable").unlink()

            result = stage_patch_workdir(game_dir, work, require_repack_plan=True)

        self.assertFalse(result.ok)
        self.assertTrue(any("repack dry-run plan is required" in error for error in result.errors))
        self.assertTrue(any(step.id == "repack_preflight" and step.status == "blocked" for step in result.steps))

    def test_save_patch_stage_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            result = stage_patch_workdir(game_dir, work)
            output = root / "stage-result.json"

            save_patch_stage_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["steps"][0]["id"], "backup_preflight")


def _make_game_dir(root: Path) -> Path:
    game_dir = root / "game"
    game_dir.mkdir()
    (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
    return game_dir


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
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


def _make_text_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted" / "BigFile_PC_exp").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text(
        '{"a":"Hello\\nNi hao"}',
        encoding="utf-8",
    )
    (work / "extracted" / "BigFile_PC_exp" / "0x00000000.txt").write_text(
        "a=Old\r\n",
        encoding="utf-8",
    )
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


if __name__ == "__main__":
    unittest.main()
