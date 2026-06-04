from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from dbh_bisub.patch_materialize import materialize_patch_package, save_patch_materialize_result
from dbh_bisub.patch_package import package_patch_workdir


class PatchMaterializeTest(unittest.TestCase):
    def test_materialize_copies_package_to_extracted_and_records_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            package_patch_workdir(work)

            result = materialize_patch_package(work)
            target = work / "extracted" / "ChineseTraditional.json"
            target_text = target.read_text(encoding="utf-8")
            manifest = json.loads((work / "reports" / "materialize-manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(result.ok)
        self.assertEqual(target_text, "patched")
        self.assertEqual(result.files[0].relative_path, "ChineseTraditional.json")
        self.assertNotEqual(result.files[0].original_sha256, result.files[0].patched_sha256)
        self.assertEqual(manifest["files"][0]["patched_sha256"], _sha256_text("patched"))

    def test_materialize_blocks_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            package_patch_workdir(work)
            (work / "package" / "ChineseTraditional.json").write_text("tampered", encoding="utf-8")

            result = materialize_patch_package(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("hash mismatch" in error for error in result.errors))

    def test_materialize_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            package_patch_workdir(work)
            manifest_path = work / "reports" / "package-manifest.json"
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["files"][0]["relative_path"] = "../outside.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")

            result = materialize_patch_package(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("outside extracted directory" in error for error in result.errors))

    def test_materialize_requires_existing_extracted_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            package_patch_workdir(work)
            (work / "extracted" / "ChineseTraditional.json").unlink()

            result = materialize_patch_package(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Extracted target file does not exist" in error for error in result.errors))

    def test_materialize_removes_text_sibling_for_dat_only_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = root / "work"
            generated = work / "generated" / "BigFile_PC_exp"
            extracted = work / "extracted" / "BigFile_PC_exp"
            generated.mkdir(parents=True)
            extracted.mkdir(parents=True)
            (work / "reports").mkdir(parents=True)
            (generated / "0x00000000.dat").write_bytes(b"patched dat")
            (extracted / "0x00000000.dat").write_bytes(b"original dat")
            (extracted / "0x00000000.txt").write_text("stale text", encoding="utf-8")
            package_patch_workdir(work)

            result = materialize_patch_package(work)
            text_sibling_exists = (extracted / "0x00000000.txt").exists()
            target_bytes = (extracted / "0x00000000.dat").read_bytes()

        self.assertTrue(result.ok)
        self.assertFalse(text_sibling_exists)
        self.assertEqual(target_bytes, b"patched dat")
        self.assertEqual(len(result.suppressed_files), 1)

    def test_save_patch_materialize_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            package_patch_workdir(work)
            result = materialize_patch_package(work)
            output = root / "result.json"

            save_patch_materialize_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["files"][0]["relative_path"], "ChineseTraditional.json")


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "generated").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "generated" / "ChineseTraditional.json").write_text("patched", encoding="utf-8")
    (work / "extracted" / "ChineseTraditional.json").write_text("original", encoding="utf-8")
    return work


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
