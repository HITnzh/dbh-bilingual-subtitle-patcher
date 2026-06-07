from pathlib import Path
import json
import tempfile
import unittest

from dbh_bisub.idx_dat_language_patch import normalize_language_code, patch_idx_dat_language_tree


class IdxDatLanguagePatchTest(unittest.TestCase):
    def test_normalizes_chinese_aliases(self) -> None:
        self.assertEqual(normalize_language_code("CHT"), "CHI")
        self.assertEqual(normalize_language_code("chs"), "SCH")

    def test_patches_only_requested_language_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "bilingual.json"
            extracted = root / "extracted" / "BigFile_PC_exp"
            output = root / "generated"
            extracted.mkdir(parents=True)
            source.write_text(
                json.dumps({"HELLO_KEY": "Hello / Ni hao", "BYE_KEY": "Bye / Zai jian"}),
                encoding="utf-8",
            )
            (extracted / "0x00000000.dat").write_bytes(
                _language_block("ENG", {"HELLO_KEY": "{S}Hello", "BYE_KEY": "{S}Bye"})
                + _language_block("CHI", {"HELLO_KEY": "{S}Ni hao", "BYE_KEY": "{S}Zai jian"})
                + _language_block("SCH", {"HELLO_KEY": "{S}Ni hao simplified", "BYE_KEY": "{S}Zai jian simplified"})
            )

            result = patch_idx_dat_language_tree(
                source=source,
                extracted_dir=root / "extracted",
                output_dir=output,
                language="CHT",
            )
            patched = (output / "BigFile_PC_exp" / "0x00000000.dat").read_bytes()

        self.assertTrue(result.ok)
        self.assertEqual(result.report.language, "CHI")
        self.assertEqual(result.report.updated, 2)
        self.assertIn("{S}Hello / Ni hao".encode("utf-16le"), patched)
        self.assertIn("{S}Bye / Zai jian".encode("utf-16le"), patched)
        self.assertIn("{S}Hello".encode("utf-16le"), patched)
        self.assertIn("{S}Ni hao simplified".encode("utf-16le"), patched)

    def test_patches_records_with_padding_between_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "bilingual.json"
            extracted = root / "extracted" / "BigFile_PC_exp"
            output = root / "generated"
            extracted.mkdir(parents=True)
            source.write_text(json.dumps({"SECOND_KEY": "Second / Di er"}), encoding="utf-8")
            (extracted / "0x00000000.dat").write_bytes(
                _language_block(
                    "CHI",
                    {"FIRST_KEY": "{S}Di yi", "SECOND_KEY": "{S}Di er"},
                    gap=b"\xAA\xBB\xCC\xDD",
                )
            )

            result = patch_idx_dat_language_tree(
                source=source,
                extracted_dir=root / "extracted",
                output_dir=output,
                language="CHI",
            )
            patched = (output / "BigFile_PC_exp" / "0x00000000.dat").read_bytes()

        self.assertTrue(result.ok)
        self.assertEqual(result.report.target_entries, 2)
        self.assertEqual(result.report.updated, 1)
        self.assertEqual(result.report.missing_in_source, 1)
        self.assertIn(b"\xAA\xBB\xCC\xDD", patched)
        self.assertIn("{S}Second / Di er".encode("utf-16le"), patched)

    def test_patches_language_record_header_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "bilingual.json"
            extracted = root / "extracted" / "BigFile_PC_exp"
            output = root / "generated"
            extracted.mkdir(parents=True)
            source.write_text(json.dumps({"HELLO_KEY": "Hello{B}你好"}), encoding="utf-8")
            (extracted / "0x00000000.dat").write_bytes(
                _record("ENG", "header")
                + _record("HELLO_KEY", "{S}Hello")
                + b"\xAA\xBB"
                + _record("SCH", "header")
                + b"\xCC\xDD"
                + _record("HELLO_KEY", "{S}你好")
            )

            result = patch_idx_dat_language_tree(
                source=source,
                extracted_dir=root / "extracted",
                output_dir=output,
                language="SCH",
            )
            patched = (output / "BigFile_PC_exp" / "0x00000000.dat").read_bytes()

        self.assertTrue(result.ok)
        self.assertEqual(result.report.updated, 1)
        self.assertIn("{S}Hello{B}你好".encode("utf-16le"), patched)
        self.assertIn("{S}Hello".encode("utf-16le"), patched)
        self.assertIn(b"\xCC\xDD", patched)


def _language_block(language: str, values: dict[str, str], gap: bytes = b"") -> bytes:
    block = b"\x01\x03\x00\x00\x00" + language.encode("ascii") + b"\x12\x00\x00\x00"
    for index, (key, value) in enumerate(values.items()):
        if index:
            block += gap
        key_bytes = key.encode("ascii")
        value_bytes = value.encode("utf-16le")
        block += len(key_bytes).to_bytes(4, "little") + key_bytes
        block += len(value_bytes).to_bytes(4, "little") + value_bytes
    return block


def _record(key: str, value: str) -> bytes:
    key_bytes = key.encode("ascii")
    value_bytes = value.encode("utf-16le")
    return len(key_bytes).to_bytes(4, "little") + key_bytes + len(value_bytes).to_bytes(4, "little") + value_bytes


if __name__ == "__main__":
    unittest.main()
