from pathlib import Path
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
