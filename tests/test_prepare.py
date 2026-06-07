from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.hash_manifest import save_hash_manifest, snapshot_hash_manifest
from dbh_bisub.prepare import prepare_patch_workdir


class PrepareTest(unittest.TestCase):
    def test_prepare_patch_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            work_dir = root / "work"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello\\n你好"}]}', encoding="utf-8")
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))
            idx_detroit = root / "IDX_Detroit.exe"
            idx_detroit.write_text("fake", encoding="utf-8")

            result = prepare_patch_workdir(
                game_dir,
                catalog=catalog,
                work_dir=work_dir,
                hash_manifest=manifest_path,
                idx_detroit=idx_detroit,
            )
            staged_catalog = Path(result.layout.catalog_path)
            plan_path = Path(result.layout.patch_plan_path)
            report_path = Path(result.layout.prepare_result_path)
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            staged_catalog_exists = staged_catalog.exists()
            plan_exists = plan_path.exists()
            report_exists = report_path.exists()

        self.assertTrue(result.ok)
        self.assertTrue(staged_catalog_exists)
        self.assertTrue(plan_exists)
        self.assertTrue(report_exists)
        self.assertEqual(plan_data["catalog_entries"], 1)
        self.assertIn(str(report_path), result.written_files)

    def test_prepare_rejects_non_empty_workdir_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            work_dir = root / "work"
            game_dir.mkdir()
            work_dir.mkdir()
            (work_dir / "existing.txt").write_text("existing", encoding="utf-8")
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello"}]}', encoding="utf-8")

            result = prepare_patch_workdir(game_dir, catalog=catalog, work_dir=work_dir)

        self.assertFalse(result.ok)
        self.assertTrue(any("not empty" in error for error in result.errors))

    def test_prepare_force_reuses_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            work_dir = root / "work"
            game_dir.mkdir()
            work_dir.mkdir()
            (work_dir / "existing.txt").write_text("existing", encoding="utf-8")
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello"}]}', encoding="utf-8")

            result = prepare_patch_workdir(game_dir, catalog=catalog, work_dir=work_dir, force=True)
            staged_catalog_exists = Path(result.layout.catalog_path).exists()

        self.assertTrue(result.ok)
        self.assertTrue(staged_catalog_exists)

    def test_prepare_force_allows_existing_patch_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            work_dir = root / "work"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            (game_dir / "BigFile_PC.d30").write_bytes(b"patch")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello"}]}', encoding="utf-8")

            result = prepare_patch_workdir(game_dir, catalog=catalog, work_dir=work_dir, force=True)

        self.assertTrue(result.ok)

    def test_prepare_blocks_on_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            manifest_path = root / "hashes.json"
            save_hash_manifest(manifest_path, snapshot_hash_manifest(game_dir, version_id="test"))
            (game_dir / "BigFile_PC.idx").write_bytes(b"changed")
            catalog = root / "bilingual.json"
            catalog.write_text('{"entries":[{"key":"a","text":"Hello"}]}', encoding="utf-8")

            result = prepare_patch_workdir(game_dir, catalog=catalog, work_dir=root / "work", hash_manifest=manifest_path)

        self.assertFalse(result.ok)
        self.assertTrue(any("hash manifest" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
