from pathlib import Path
import tempfile
import unittest

from dbh_bisub.hash_manifest import save_hash_manifest, snapshot_hash_manifest
from dbh_bisub.patcher import build_patch_plan


class PatcherTest(unittest.TestCase):
    def test_dry_run_plan_for_minimal_game_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            plan = build_patch_plan(root, dry_run=True)

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.planned_writes, ["BigFile_PC.idx", "BigFile_PC.d30"])
        self.assertIn("BigFile_PC.idx", plan.required_backups)

    def test_apply_plan_is_not_implemented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            plan = build_patch_plan(root, dry_run=False)

        self.assertFalse(plan.can_apply)
        self.assertTrue(any("not implemented" in error for error in plan.errors))

    def test_full_preflight_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello\\n你好"}]}', encoding="utf-8")
            work_dir = root / "work"
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))
            file_parser = root / "FileParser.exe"
            idx_detroit = root / "IDX_Detroit.exe"
            file_parser.write_text("fake", encoding="utf-8")
            idx_detroit.write_text("fake", encoding="utf-8")

            plan = build_patch_plan(
                game_dir,
                dry_run=True,
                catalog=catalog,
                work_dir=work_dir,
                hash_manifest=manifest_path,
                file_parser=file_parser,
                idx_detroit=idx_detroit,
            )

        self.assertTrue(plan.can_apply)
        self.assertEqual(plan.catalog_entries, 1)
        self.assertEqual(plan.hash_report["ok"], True)
        self.assertEqual(plan.toolchain["idx_detroit"]["available"], True)
        self.assertTrue(any(step.id == "prepare_work_dir" and step.status == "planned" for step in plan.steps))

    def test_hash_mismatch_blocks_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))
            (game_dir / "BigFile_PC.idx").write_bytes(b"changed")

            plan = build_patch_plan(game_dir, dry_run=True, hash_manifest=manifest_path)

        self.assertFalse(plan.can_apply)
        self.assertTrue(any("hash manifest" in error for error in plan.errors))

    def test_require_hash_blocks_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            plan = build_patch_plan(root, dry_run=True, require_hash=True)

        self.assertFalse(plan.can_apply)
        self.assertTrue(any("hash manifest is required" in error for error in plan.errors))


if __name__ == "__main__":
    unittest.main()
