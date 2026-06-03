from pathlib import Path
import tempfile
import unittest

from dbh_bisub.hash_manifest import (
    compare_hash_manifest,
    load_hash_manifest,
    save_hash_manifest,
    snapshot_hash_manifest,
)


class HashManifestTest(unittest.TestCase):
    def test_snapshot_excludes_patch_archive_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")
            (root / "BigFile_PC.d30").write_bytes(b"patch")

            manifest = snapshot_hash_manifest(root, version_id="steam-test")

        self.assertEqual(manifest.version_id, "steam-test")
        self.assertEqual([entry.name for entry in manifest.files], ["BigFile_PC.d00", "BigFile_PC.idx"])

    def test_save_load_and_compare_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            manifest = snapshot_hash_manifest(root, version_id="local")
            save_hash_manifest(manifest_path, manifest)
            loaded = load_hash_manifest(manifest_path)
            report = compare_hash_manifest(root, loaded)

        self.assertTrue(report.ok)
        self.assertEqual(report.missing, [])
        self.assertEqual(report.mismatched, [])
        self.assertEqual(report.matched, ["BigFile_PC.d00", "BigFile_PC.idx"])

    def test_compare_reports_mismatch_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            manifest = snapshot_hash_manifest(root, version_id="local")
            (root / "BigFile_PC.idx").write_bytes(b"changed")
            (root / "BigFile_PC.d00").unlink()
            report = compare_hash_manifest(root, manifest)

        self.assertFalse(report.ok)
        self.assertEqual(report.missing, ["BigFile_PC.d00"])
        self.assertEqual([item.name for item in report.mismatched], ["BigFile_PC.idx"])

    def test_compare_reports_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            manifest = snapshot_hash_manifest(root, version_id="local")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            report = compare_hash_manifest(root, manifest)

        self.assertTrue(report.ok)
        self.assertEqual(report.extra, ["BigFile_PC.d00"])
        self.assertTrue(report.warnings)


if __name__ == "__main__":
    unittest.main()
