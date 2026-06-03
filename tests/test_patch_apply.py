from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from dbh_bisub.idx_archive import IdxResult
from dbh_bisub.patch_apply import apply_patch_workflow, save_patch_apply_result


class PatchApplyTest(unittest.TestCase):
    def test_apply_defaults_to_repack_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = apply_patch_workflow(game_dir, work, idx_detroit=tool)
            materialized_data = json.loads((work / "extracted" / "ChineseTraditional.json").read_text(encoding="utf-8"))
            package_manifest_exists = (work / "reports" / "package-manifest.json").exists()
            materialize_manifest_exists = (work / "reports" / "materialize-manifest.json").exists()

        self.assertTrue(result.ok)
        self.assertFalse(result.execute_repack)
        self.assertEqual(result.stage["injection"]["injection"]["report"]["updated"], 1)
        self.assertEqual(result.materialize["files"][0]["relative_path"], "ChineseTraditional.json")
        self.assertTrue(result.repack["repack"]["plan"]["dry_run"])
        self.assertIsNone(result.repack["backup_manifest"])
        self.assertEqual(materialized_data["entries"][0]["text"], "Hello\n你好")
        self.assertTrue(package_manifest_exists)
        self.assertTrue(materialize_manifest_exists)
        self.assertTrue(any(step.id == "repack" and step.status == "ready" for step in result.steps))

    def test_apply_execute_repack_creates_backup_before_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            def fake_run(plan):
                self.assertFalse(plan.dry_run)
                return IdxResult(plan=plan, returncode=0, stdout="ok", stderr="")

            with patch("dbh_bisub.patch_repack.run_idx_plan", side_effect=fake_run):
                result = apply_patch_workflow(
                    game_dir,
                    work,
                    idx_detroit=tool,
                    backup_id="test-backup",
                    execute_repack=True,
                )
            backup_manifest_exists = (game_dir / ".dbh-bisub-backups" / "test-backup" / "manifest.json").exists()

        self.assertTrue(result.ok)
        self.assertTrue(result.execute_repack)
        self.assertIsNotNone(result.repack["backup_manifest"])
        self.assertEqual(result.repack["repack"]["returncode"], 0)
        self.assertTrue(backup_manifest_exists)
        self.assertTrue(any(step.id == "repack" and step.status == "done" for step in result.steps))

    def test_apply_stops_when_stage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = apply_patch_workflow(root / "missing-game", work, idx_detroit=tool)

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.stage)
        self.assertIsNone(result.materialize)
        self.assertIsNone(result.repack)
        self.assertTrue(any("Patch staging failed" in error for error in result.errors))

    def test_apply_can_save_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")
            result = apply_patch_workflow(game_dir, work, idx_detroit=tool)
            output = root / "apply-result.json"

            save_patch_apply_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["steps"][0]["id"], "stage")


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


if __name__ == "__main__":
    unittest.main()
