from pathlib import Path
import json
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from dbh_bisub.patch_extract import extract_patch_workdir, save_patch_extract_result


class PatchExtractTest(unittest.TestCase):
    def test_extract_dry_run_targets_workdir_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = extract_patch_workdir(game_dir, work, idx_detroit=tool)

        self.assertTrue(result.ok)
        self.assertFalse(result.execute)
        self.assertTrue(result.idx_extract["plan"]["dry_run"] if "plan" in result.idx_extract else result.idx_extract["dry_run"])
        self.assertEqual(result.extracted_dir, str(work / "extracted"))
        self.assertIsNone(result.returncode)

    def test_extract_rejects_non_empty_extracted_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            (work / "extracted" / "existing.bin").write_bytes(b"existing")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = extract_patch_workdir(game_dir, work, idx_detroit=tool)

        self.assertFalse(result.ok)
        self.assertTrue(any("not empty" in error for error in result.errors))

    def test_extract_execute_runs_with_extracted_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            def fake_run(command, **kwargs):
                self.assertEqual(kwargs["cwd"], work / "extracted")
                self.assertIn(str(game_dir / "BigFile_PC.idx"), command)
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with patch("dbh_bisub.patch_extract.subprocess.run", side_effect=fake_run):
                result = extract_patch_workdir(game_dir, work, idx_detroit=tool, execute=True)

        self.assertTrue(result.ok)
        self.assertTrue(result.execute)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok")

    def test_extract_execute_reports_process_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            with patch("dbh_bisub.patch_extract.subprocess.run", return_value=SimpleNamespace(returncode=7, stdout="", stderr="bad")):
                result = extract_patch_workdir(game_dir, work, idx_detroit=tool, execute=True)

        self.assertFalse(result.ok)
        self.assertEqual(result.returncode, 7)
        self.assertTrue(any("extract failed" in error for error in result.errors))

    def test_save_patch_extract_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            game_dir = _make_game_dir(root)
            work = _make_workdir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")
            result = extract_patch_workdir(game_dir, work, idx_detroit=tool)
            output = root / "result.json"

            save_patch_extract_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["extracted_dir"], str(work / "extracted"))


def _make_game_dir(root: Path) -> Path:
    game_dir = root / "game"
    game_dir.mkdir()
    (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
    return game_dir


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "extracted").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    return work


if __name__ == "__main__":
    unittest.main()
