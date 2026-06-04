from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.patch_inject import patch_inject_workdir, save_patch_inject_result


class PatchInjectTest(unittest.TestCase):
    def test_patch_inject_auto_discovers_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))

            result = patch_inject_workdir(work)
            output = Path(result.output)
            report_path = Path(result.report_path)
            patched = json.loads(output.read_text(encoding="utf-8"))
            report_exists = report_path.exists()

        self.assertTrue(result.ok)
        self.assertEqual(patched["entries"][0]["text"], "Hello\n你好")
        self.assertTrue(report_exists)
        self.assertEqual(result.injection["report"]["updated"], 1)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.discovery["warnings"], [])

    def test_patch_inject_rejects_multiple_chinese_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "extracted" / "zh-Hans.json").write_text('{"a":"你好"}', encoding="utf-8")

            result = patch_inject_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Multiple Chinese" in error for error in result.errors))

    def test_patch_inject_accepts_explicit_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            extra = work / "extracted" / "zh-Hans.json"
            extra.write_text('{"a":"你好"}', encoding="utf-8")

            result = patch_inject_workdir(work, target=Path("ChineseTraditional.json"))
            patched = json.loads(Path(result.output).read_text(encoding="utf-8"))

        self.assertTrue(result.ok)
        self.assertEqual(patched["entries"][0]["text"], "Hello\n你好")

    def test_patch_inject_blocks_when_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_workdir(Path(temp_dir))
            (work / "catalog" / "bilingual.json").unlink()

            result = patch_inject_workdir(work)

        self.assertFalse(result.ok)
        self.assertTrue(any("Bilingual catalog does not exist" in error for error in result.errors))

    def test_patch_inject_falls_back_to_idx_text_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_text_workdir(Path(temp_dir))

            result = patch_inject_workdir(work)
            patched = (work / "generated" / "BigFile_PC_exp" / "0x00000000.txt").read_text(encoding="utf-8")

        self.assertTrue(result.ok)
        self.assertEqual(result.injection["mode"], "idx_text")
        self.assertEqual(result.injection["report"]["updated"], 1)
        self.assertEqual(result.injection["report"]["unchanged"], 1)
        self.assertIn("a=Hello[n]Ni hao", patched)
        self.assertIn("b=Use[p]thing", patched)
        self.assertIn("c=Keep", patched)

    def test_patch_inject_can_patch_idx_dat_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work = _make_text_workdir(Path(temp_dir))
            (work / "catalog" / "bilingual.json").write_text(
                '{"HELLO_KEY":"Hello\\nNi hao","USE_KEY":"Use=thing"}',
                encoding="utf-8",
            )
            (work / "extracted" / "BigFile_PC_exp" / "0x00000000.txt").write_text(
                "HELLO_KEY=Old\r\nUSE_KEY=Use[p]thing\r\n",
                encoding="utf-8",
            )
            (work / "extracted" / "BigFile_PC_exp" / "0x00000000.dat").write_bytes(
                _language_block("ENG", {"HELLO_KEY": "{S}Old", "USE_KEY": "{S}Use thing"})
                + _language_block("CHI", {"HELLO_KEY": "{S}Ni hao", "USE_KEY": "{S}Use thing"})
            )

            result = patch_inject_workdir(work, idx_dat_language="CHT")
            patched = (work / "generated" / "BigFile_PC_exp" / "0x00000000.dat").read_bytes()
            text_output_exists = (work / "generated" / "BigFile_PC_exp" / "0x00000000.txt").exists()

        self.assertTrue(result.ok)
        self.assertEqual(result.injection["dat_language"]["report"]["language"], "CHI")
        self.assertEqual(result.injection["dat_language"]["report"]["updated"], 2)
        self.assertFalse(text_output_exists)
        self.assertEqual(len(result.injection["dat_language"]["suppressed_text_outputs"]), 1)
        self.assertIn("{S}Hello\nNi hao".encode("utf-16le"), patched)
        self.assertIn("{S}Use=thing".encode("utf-16le"), patched)

    def test_save_patch_inject_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            work = _make_workdir(root)
            result = patch_inject_workdir(work)
            output = root / "result.json"

            save_patch_inject_result(output, result)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertTrue(data["ok"])
        self.assertEqual(data["injection"]["report"]["updated"], 1)


def _make_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text('{"a":"Hello\\n你好"}', encoding="utf-8")
    (work / "extracted" / "ChineseTraditional.json").write_text(
        '{"entries":[{"key":"a","text":"你好","speaker":"Connor"}]}',
        encoding="utf-8",
    )
    return work


def _make_text_workdir(root: Path) -> Path:
    work = root / "work"
    (work / "catalog").mkdir(parents=True)
    (work / "extracted" / "BigFile_PC_exp").mkdir(parents=True)
    (work / "generated").mkdir(parents=True)
    (work / "reports").mkdir(parents=True)
    (work / "catalog" / "bilingual.json").write_text(
        '{"a":"Hello\\nNi hao","b":"Use=thing"}',
        encoding="utf-8",
    )
    (work / "extracted" / "BigFile_PC_exp" / "0x00000000.txt").write_text(
        "a=Old\r\nb=Use[p]thing\r\nc=Keep\r\nnot-an-entry\r\n",
        encoding="utf-8",
    )
    return work


def _language_block(language: str, values: dict[str, str]) -> bytes:
    block = b"\x01\x03\x00\x00\x00" + language.encode("ascii") + b"\x12\x00\x00\x00"
    for key, value in values.items():
        key_bytes = key.encode("ascii")
        value_bytes = value.encode("utf-16le")
        block += len(key_bytes).to_bytes(4, "little") + key_bytes
        block += len(value_bytes).to_bytes(4, "little") + value_bytes
    return block


if __name__ == "__main__":
    unittest.main()
