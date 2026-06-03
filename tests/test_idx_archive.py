from pathlib import Path
import tempfile
import unittest

from dbh_bisub.idx_archive import default_idx_file, plan_idx_extract, plan_idx_repack, run_idx_plan


class IdxArchiveTest(unittest.TestCase):
    def test_default_idx_file(self) -> None:
        self.assertEqual(default_idx_file("game"), Path("game") / "BigFile_PC.idx")

    def test_plan_extract_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            idx_file = root / "BigFile_PC.idx"
            idx_file.write_bytes(b"idx")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_idx_extract(idx_file, idx_detroit=tool, archive_id=1, object_count=0, dry_run=True)

        self.assertTrue(plan.ok)
        self.assertEqual(plan.action, "extract")
        self.assertEqual(plan.command[-3:], [str(idx_file), "1", "0"])

    def test_plan_extract_rejects_negative_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            idx_file = root / "BigFile_PC.idx"
            idx_file.write_bytes(b"idx")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_idx_extract(idx_file, idx_detroit=tool, archive_id=-1, object_count=-2)

        self.assertFalse(plan.ok)
        self.assertEqual(len([error for error in plan.errors if "must be non-negative" in error]), 2)

    def test_plan_repack_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            idx_file = root / "BigFile_PC.idx"
            table = root / "BigFile_PC.FileSizeTable"
            idx_file.write_bytes(b"idx")
            table.write_text("table", encoding="utf-8")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_idx_repack(idx_file, table, idx_detroit=tool, dry_run=True)

        self.assertTrue(plan.ok)
        self.assertEqual(plan.action, "repack")
        self.assertEqual(plan.command[-2:], [str(idx_file), str(table)])

    def test_plan_repack_requires_file_size_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            idx_file = root / "BigFile_PC.idx"
            idx_file.write_bytes(b"idx")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_idx_repack(idx_file, root / "missing.FileSizeTable", idx_detroit=tool)

        self.assertFalse(plan.ok)
        self.assertTrue(any("FileSizeTable does not exist" in error for error in plan.errors))

    def test_run_idx_dry_run_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            idx_file = root / "BigFile_PC.idx"
            idx_file.write_bytes(b"idx")
            tool = root / "IDX_Detroit.exe"
            tool.write_text("fake", encoding="utf-8")

            plan = plan_idx_extract(idx_file, idx_detroit=tool, dry_run=True)
            result = run_idx_plan(plan)

        self.assertTrue(result.ok)
        self.assertIsNone(result.returncode)


if __name__ == "__main__":
    unittest.main()
