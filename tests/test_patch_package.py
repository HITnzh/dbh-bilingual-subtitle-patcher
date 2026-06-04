from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.patch_package import package_patch_workdir, save_patch_package_result


class PatchPackageTest(unittest.TestCase):
    def test_package_copies_generated_files_and_plans_repack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            game_dir = _make_game_dir(root)
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = package_patch_workdir(
                work,
                game_dir=game_dir,
                idx_detroit=tool,
            )
            packaged = Path(result.files[0].packaged)
            manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
            packaged_exists = packaged.exists()

        self.assertTrue(result.ok)
        self.assertTrue(packaged_exists)
        self.assertEqual(result.files[0].relative_path, "ChineseTraditional.json")
        self.assertEqual(result.files[0].size, len(b"patched"))
        self.assertEqual(manifest["files"][0]["sha256"], result.files[0].sha256)
        self.assertEqual(result.repack_plan["action"], "repack")
        self.assertTrue(result.repack_plan["ok"])

    def test_package_reads_game_dir_from_prepare_patch_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            game_dir = _make_game_dir(root)
            (work / "reports" / "patch-plan.json").write_text(
                json.dumps({"game_dir": str(game_dir)}),
                encoding="utf-8",
            )
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            result = package_patch_workdir(work, idx_detroit=tool)

        self.assertTrue(result.ok)
        self.assertEqual(result.idx_file, str(game_dir / "BigFile_PC.idx"))
        self.assertTrue(result.repack_plan["ok"])

    def test_package_blocks_when_generated_directory_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = root / "work"
            (work / "generated").mkdir(parents=True)

            result = package_patch_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("contains no files" in error for error in result.errors))

    def test_package_allows_manifest_without_repack_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = root / "work"
            (work / "generated").mkdir(parents=True)
            (work / "reports").mkdir(parents=True)
            (work / "generated" / "ChineseTraditional.json").write_text("patched", encoding="utf-8")

            result = package_patch_workdir(work)
            manifest_exists = Path(result.manifest_path).exists()

        self.assertTrue(result.ok)
        self.assertTrue(manifest_exists)
        self.assertIsNone(result.repack_plan)
        self.assertTrue(any("FileSizeTable" in warning for warning in result.warnings))

    def test_package_cleans_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            stale = work / "package" / "stale.txt"
            stale.parent.mkdir()
            stale.write_text("old", encoding="utf-8")

            result = package_patch_workdir(work)
            stale_exists = stale.exists()

        self.assertTrue(result.ok)
        self.assertFalse(stale_exists)
        self.assertEqual([file.relative_path for file in result.files], ["ChineseTraditional.json"])

    def test_package_refuses_to_clean_outside_workdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            outside = root / "outside-package"
            outside.mkdir()
            (outside / "keep.txt").write_text("old", encoding="utf-8")

            result = package_patch_workdir(work, package_dir=outside)
            outside_file_exists = (outside / "keep.txt").exists()

        self.assertFalse(result.ok)
        self.assertTrue(outside_file_exists)
        self.assertTrue(any("outside work directory" in error for error in result.errors))

    def test_save_patch_package_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            result = package_patch_workdir(work)
            output = root / "result.json"

            save_patch_package_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["files"][0]["relative_path"], "ChineseTraditional.json")


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "generated" / "ChineseTraditional.json").write_text("patched", encoding="utf-8")
    (work / "extracted" / "BigFile_PC.FileSizeTable").write_text("table", encoding="utf-8")
    return work


def _make_game_dir(root: Path) -> Path:
    game_dir = root / "game"
    game_dir.mkdir()
    (game_dir / "BigFile_PC.idx").write_bytes(b"idx")
    return game_dir


if __name__ == "__main__":
    unittest.main()
