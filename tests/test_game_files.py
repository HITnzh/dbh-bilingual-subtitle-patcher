from pathlib import Path
import tempfile
import unittest

from dbh_bisub.game_files import inspect_game_dir


class GameFilesTest(unittest.TestCase):
    def test_inspect_missing_game_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = inspect_game_dir(Path(temp_dir) / "missing")

        self.assertFalse(report.ok)
        self.assertTrue(report.errors)

    def test_inspect_valid_minimal_game_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")

            report = inspect_game_dir(root)

        self.assertTrue(report.ok)
        self.assertTrue(report.index.exists)
        self.assertEqual([archive.name for archive in report.archives], ["BigFile_PC.d00"])

    def test_warns_when_patch_archive_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "BigFile_PC.idx").write_bytes(b"idx")
            (root / "BigFile_PC.d00").write_bytes(b"archive")
            (root / "BigFile_PC.d30").write_bytes(b"patch")

            report = inspect_game_dir(root)

        self.assertTrue(report.ok)
        self.assertTrue(any("BigFile_PC.d30 already exists" in warning for warning in report.warnings))


if __name__ == "__main__":
    unittest.main()
