from pathlib import Path
import tempfile
import unittest

from dbh_bisub.toolchain import (
    FILE_PARSER,
    build_file_parser_extract_command,
    build_idx_extract_command,
    build_idx_repack_command,
    format_command,
    inspect_toolchain,
    probe_tool,
)


class ToolchainTest(unittest.TestCase):
    def test_probe_explicit_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            executable = Path(temp_dir) / "FileParser.exe"
            executable.write_text("fake", encoding="utf-8")

            result = probe_tool(FILE_PARSER, executable)

        self.assertTrue(result.available)
        self.assertEqual(result.source, "explicit")
        self.assertTrue(result.resolved_path.endswith("FileParser.exe"))

    def test_probe_explicit_missing_file(self) -> None:
        result = probe_tool(FILE_PARSER, Path("missing.exe"))

        self.assertFalse(result.available)
        self.assertTrue(result.errors)

    def test_inspect_toolchain_reports_two_tools(self) -> None:
        report = inspect_toolchain()

        self.assertEqual([tool.id for tool in report.tools], ["file_parser", "idx_detroit"])

    def test_build_file_parser_extract_command(self) -> None:
        command = build_file_parser_extract_command("FileParser", "game", "out", verbose=True)

        self.assertEqual(command, ["FileParser", "-v", "-i", "game", "-o", "out"])

    def test_build_idx_commands(self) -> None:
        self.assertEqual(
            build_idx_extract_command("IDX_Detroit.exe", "BigFile_PC.idx", archive_id=1, object_count=0),
            ["IDX_Detroit.exe", "-e", "BigFile_PC.idx", "1", "0"],
        )
        self.assertEqual(
            build_idx_repack_command("IDX_Detroit.exe", "BigFile_PC.idx", "table.FileSizeTable"),
            ["IDX_Detroit.exe", "-p", "BigFile_PC.idx", "table.FileSizeTable"],
        )

    def test_format_command_quotes_spaces(self) -> None:
        formatted = format_command(["FileParser", "-i", "C:/Program Files/Game"])

        self.assertIn('"C:/Program Files/Game"', formatted)


if __name__ == "__main__":
    unittest.main()
