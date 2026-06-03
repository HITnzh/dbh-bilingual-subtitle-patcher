from pathlib import Path
import tempfile
import unittest

from dbh_bisub.extractor import plan_extraction, run_extraction


class ExtractorTest(unittest.TestCase):
    def test_plan_extraction_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            tool = root / "FileParser.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_extraction(game_dir, root / "output", file_parser=tool, dry_run=True)

        self.assertTrue(plan.ok)
        self.assertIn("-i", plan.command)
        self.assertIn("-o", plan.command)

    def test_plan_extraction_rejects_non_empty_output_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            output_dir = root / "output"
            game_dir.mkdir()
            output_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            (output_dir / "existing.json").write_text("{}", encoding="utf-8")
            tool = root / "FileParser.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_extraction(game_dir, output_dir, file_parser=tool, dry_run=True)

        self.assertFalse(plan.ok)
        self.assertTrue(any("not empty" in error for error in plan.errors))

    def test_plan_extraction_allows_non_empty_output_with_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            output_dir = root / "output"
            game_dir.mkdir()
            output_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            (output_dir / "existing.json").write_text("{}", encoding="utf-8")
            tool = root / "FileParser.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_extraction(game_dir, output_dir, file_parser=tool, dry_run=True, force=True)

        self.assertTrue(plan.ok)

    def test_run_extraction_dry_run_does_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            output_dir = root / "output"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            tool = root / "FileParser.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_extraction(game_dir, output_dir, file_parser=tool, dry_run=True)
            result = run_extraction(plan)

            self.assertTrue(result.ok)
            self.assertIsNone(result.returncode)
            self.assertFalse(output_dir.exists())

    def test_run_extraction_reports_process_start_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = root / "game"
            output_dir = root / "output"
            game_dir.mkdir()
            (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
            (game_dir / "BigFile_PC.d00").write_bytes(b"archive")
            tool = root / "FileParser.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_extraction(game_dir, output_dir, file_parser=tool, dry_run=False)
            result = run_extraction(plan)

            self.assertFalse(result.ok)
            self.assertEqual(result.returncode, -1)
            self.assertTrue(result.stderr)


if __name__ == "__main__":
    unittest.main()
