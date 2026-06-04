from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from dbh_bisub.hash_manifest import save_hash_manifest, snapshot_hash_manifest
from dbh_bisub.idx_archive import IdxResult
from dbh_bisub.patch_materialize import materialize_patch_package
from dbh_bisub.patch_package import package_patch_workdir
from dbh_bisub.patch_repack import repack_patch_workdir, save_patch_repack_result


class PatchRepackTest(unittest.TestCase):
    def test_repack_defaults_to_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_materialized_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = repack_patch_workdir(game_dir, work, idx_detroit=tool)

        self.assertTrue(result.ok)
        self.assertFalse(result.execute)
        self.assertIsNone(result.backup_manifest)
        self.assertTrue(result.repack["plan"]["dry_run"])
        self.assertIsNone(result.repack["returncode"])

    def test_repack_requires_materialize_manifest_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = repack_patch_workdir(game_dir, work, idx_detroit=tool)

        self.assertFalse(result.ok)
        self.assertTrue(any("Materialize manifest does not exist" in error for error in result.errors))

    def test_repack_can_allow_unmaterialized_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = repack_patch_workdir(game_dir, work, idx_detroit=tool, allow_unmaterialized=True)

        self.assertTrue(result.ok)
        self.assertTrue(any("Materialize manifest" in warning for warning in result.warnings))
        self.assertTrue(result.repack["plan"]["dry_run"])

    def test_repack_execute_creates_backup_before_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_materialized_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))

            def fake_run(plan):
                self.assertFalse(plan.dry_run)
                (work / "extracted" / "BigFile_PC.d30").write_bytes(b"patch archive")
                return IdxResult(plan=plan, returncode=0, stdout="ok", stderr="")

            with patch("dbh_bisub.patch_repack.run_idx_plan", side_effect=fake_run):
                result = repack_patch_workdir(
                    game_dir,
                    work,
                    idx_detroit=tool,
                    hash_manifest=manifest_path,
                    backup_id="test-backup",
                    execute=True,
                )
            backup_manifest = game_dir / ".dbh-bisub-backups" / "test-backup" / "manifest.json"
            backup_manifest_exists = backup_manifest.exists()
            patch_archive_installed = (game_dir / "BigFile_PC.d30").read_bytes()

        self.assertTrue(result.ok)
        self.assertTrue(result.execute)
        self.assertIsNotNone(result.backup_manifest)
        self.assertEqual(result.repack["returncode"], 0)
        self.assertTrue(backup_manifest_exists)
        self.assertEqual(patch_archive_installed, b"patch archive")
        self.assertTrue(any(step.id == "create_backup" and step.status == "done" for step in result.steps))
        self.assertTrue(any(step.id == "install_patch_archive" and step.status == "done" for step in result.steps))

    def test_repack_execute_requires_repacked_patch_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_materialized_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))

            def fake_run(plan):
                self.assertFalse(plan.dry_run)
                return IdxResult(plan=plan, returncode=0, stdout="ok", stderr="")

            with patch("dbh_bisub.patch_repack.run_idx_plan", side_effect=fake_run):
                result = repack_patch_workdir(
                    game_dir,
                    work,
                    idx_detroit=tool,
                    hash_manifest=manifest_path,
                    execute=True,
                )

        self.assertFalse(result.ok)
        self.assertTrue(any("patch archive" in error for error in result.errors))
        self.assertTrue(any(step.id == "install_patch_archive" and step.status == "blocked" for step in result.steps))

    def test_repack_execute_requires_hash_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_materialized_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = repack_patch_workdir(game_dir, work, idx_detroit=tool, execute=True)

        self.assertFalse(result.ok)
        self.assertTrue(any("hash manifest is required" in error.lower() for error in result.errors))
        self.assertIsNone(result.backup_manifest)

    def test_save_patch_repack_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_materialized_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")
            result = repack_patch_workdir(game_dir, work, idx_detroit=tool)
            output = root / "result.json"

            save_patch_repack_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["steps"][0]["id"], "materialize_check")


def _make_game_dir(root: Path) -> Path:
    game_dir = root / "game"
    game_dir.mkdir()
    (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
    return game_dir


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "generated").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "generated" / "ChineseTraditional.json").write_text("patched", encoding="utf-8")
    (work / "extracted" / "ChineseTraditional.json").write_text("original", encoding="utf-8")
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


def _make_materialized_workdir(root: Path) -> Path:
    work = _make_workdir(root)
    package_patch_workdir(work)
    materialize_patch_package(work)
    return work


if __name__ == "__main__":
    unittest.main()
