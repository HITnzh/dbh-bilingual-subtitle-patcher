from pathlib import Path
import tempfile
import unittest

from dbh_bisub.backup_restore import create_backup, restore_backup


class BackupRestoreTest(unittest.TestCase):
    def test_create_and_restore_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "BigFile_PC.idx"
            target.write_text("original", encoding="utf-8")

            manifest = create_backup(root, ["BigFile_PC.idx"], backup_id="test-backup")
            target.write_text("patched", encoding="utf-8")
            restored = restore_backup(root, manifest.backup_id)

            self.assertEqual(restored.backup_id, "test-backup")
            self.assertEqual(target.read_text(encoding="utf-8"), "original")

    def test_restore_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "BigFile_PC.idx"
            target.write_text("original", encoding="utf-8")

            create_backup(root, ["BigFile_PC.idx"], backup_id="test-backup")
            target.write_text("patched", encoding="utf-8")
            restore_backup(root, "test-backup", dry_run=True)

            self.assertEqual(target.read_text(encoding="utf-8"), "patched")


if __name__ == "__main__":
    unittest.main()
