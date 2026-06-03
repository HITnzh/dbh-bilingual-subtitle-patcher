from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .backup_restore import DEFAULT_BACKUP_FILES, create_backup, plan_backup, restore_backup
from .catalog import load_catalog, merge_catalogs, save_catalog
from .discovery import discover_catalogs
from .extractor import plan_extraction, run_extraction
from .game_files import GameDirectoryReport, inspect_game_dir
from .patcher import PatchPlan, build_patch_plan
from .quality import (
    DEFAULT_MAX_LINE_CHARS,
    DEFAULT_MAX_LINES,
    DEFAULT_MAX_TOTAL_CHARS,
    inspect_catalog_quality,
)
from .terminology import apply_terminology_to_catalog, load_terminology
from .toolchain import (
    build_file_parser_extract_command,
    build_idx_extract_command,
    build_idx_repack_command,
    format_command,
    inspect_toolchain,
)


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_verify_report(report: GameDirectoryReport) -> None:
    print(f"Game directory: {report.game_dir}")
    print(f"Index: {'found' if report.index.exists else 'missing'} {report.index.name}")
    print(f"Archives: {len(report.archives)} found")
    for archive in report.archives:
        size = f"{archive.size} bytes" if archive.size is not None else "unknown size"
        print(f"  - {archive.name} ({size})")
    if report.backups:
        print(f"Backups: {len(report.backups)}")
        for backup_id in report.backups:
            print(f"  - {backup_id}")
    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
    if report.errors:
        print("Errors:")
        for error in report.errors:
            print(f"  - {error}")
    print(f"Status: {'ok' if report.ok else 'failed'}")


def print_patch_plan(plan: PatchPlan) -> None:
    print(f"Game directory: {plan.game_dir}")
    print(f"Mode: {'dry-run' if plan.dry_run else 'apply'}")
    if plan.planned_writes:
        print("Planned writes:")
        for name in plan.planned_writes:
            print(f"  - {name}")
    if plan.required_backups:
        print("Required backups:")
        for name in plan.required_backups:
            print(f"  - {name}")
    if plan.notes:
        print("Notes:")
        for note in plan.notes:
            print(f"  - {note}")
    if plan.warnings:
        print("Warnings:")
        for warning in plan.warnings:
            print(f"  - {warning}")
    if plan.errors:
        print("Errors:")
        for error in plan.errors:
            print(f"  - {error}")
    print(f"Status: {'ok' if plan.can_apply else 'failed'}")


def print_toolchain_report(report: Any) -> None:
    for tool in report.tools:
        print(f"{tool.display_name}: {'found' if tool.available else 'missing'}")
        print(f"  Purpose: {tool.purpose}")
        if tool.resolved_path:
            print(f"  Path: {tool.resolved_path}")
        elif tool.configured_path:
            print(f"  Configured path: {tool.configured_path}")
        else:
            print(f"  Tried: {', '.join(tool.default_names)}")
        print(f"  Docs: {tool.docs_url}")
        for warning in tool.warnings:
            print(f"  Warning: {warning}")
        for error in tool.errors:
            print(f"  Error: {error}")

    print(f"Status: {'ok' if report.ok else 'failed'}")


def print_tool_examples(args: argparse.Namespace) -> None:
    game_dir = args.game_dir or Path(".")
    output_dir = args.output_dir or Path("./output")
    idx_file = game_dir / "BigFile_PC.idx"
    file_parser = args.file_parser or "FileParser"
    idx_detroit = args.idx_detroit or "IDX_Detroit.exe"
    file_size_table = args.file_size_table or "example.FileSizeTable"

    commands = [
        build_file_parser_extract_command(file_parser, game_dir, output_dir, verbose=args.verbose_example),
        build_idx_extract_command(idx_detroit, idx_file, archive_id=args.archive_id, object_count=args.object_count),
        build_idx_repack_command(idx_detroit, idx_file, file_size_table),
    ]

    print("Example commands:")
    for command in commands:
        print(f"  {format_command(command)}")


def print_merge_report(data: dict[str, Any], output: Path, report_path: Path | None) -> None:
    print(f"Merged entries: {data['merged']}")
    print(f"English entries: {data['total_english']}")
    print(f"Chinese entries: {data['total_chinese']}")
    print(f"Missing English: {data['missing_english']}")
    print(f"Missing Chinese: {data['missing_chinese']}")
    print(f"Control token warnings: {data['token_warnings']}")
    print(f"Output: {output}")
    if report_path:
        print(f"Report: {report_path}")
    terminology = data.get("terminology")
    if terminology:
        print("Terminology:")
        print(f"  Rules loaded: {terminology['rules_loaded']}")
        print(f"  Rules matched: {terminology['rules_matched']}")
        print(f"  Replacements: {terminology['replacements']}")
        for source, count in terminology["by_source"].items():
            print(f"  - {source}: {count}")
    if data["issues"]:
        print("Issues:")
        for issue in data["issues"][:20]:
            print(f"  - [{issue['level']}] {issue['key']}: {issue['message']}")
        if len(data["issues"]) > 20:
            print(f"  - ... {len(data['issues']) - 20} more")
    print(f"Status: {'ok' if data['ok'] else 'failed'}")


def print_quality_report(data: dict[str, Any], report_path: Path | None) -> None:
    print(f"Entries: {data['entries']}")
    print(f"Issues: {data['issue_count']}")
    print(f"Warnings: {data['warnings']}")
    print(f"Errors: {data['errors']}")
    print(f"Longest line: {data['longest_line_chars']} chars")
    print(f"Longest entry: {data['longest_total_chars']} chars")
    if data["issues_by_code"]:
        print("Issues by code:")
        for code, count in data["issues_by_code"].items():
            print(f"  - {code}: {count}")
    if report_path:
        print(f"Report: {report_path}")
    if data["issues"]:
        print("Issues:")
        for issue in data["issues"][:30]:
            extra = ""
            if issue.get("limit") is not None:
                extra = f" ({issue.get('value')} > {issue.get('limit')})"
            print(f"  - [{issue['level']}] {issue['key']} {issue['code']}: {issue['message']}{extra}")
        if len(data["issues"]) > 30:
            print(f"  - ... {len(data['issues']) - 30} more")
    print(f"Status: {'ok' if data['ok'] else 'failed'}")


def print_backup_plan(data: dict[str, Any], *, dry_run: bool) -> None:
    print(f"Game directory: {data['game_dir']}")
    print(f"Backup id: {data['backup_id']}")
    print(f"Target: {data['target_dir']}")
    print(f"Mode: {'dry-run' if dry_run else 'create'}")
    if data["files_to_backup"]:
        print("Files to back up:")
        for entry in data["files_to_backup"]:
            print(f"  - {entry['source']} ({entry['size']} bytes)")
    if data["missing_files"]:
        print("Missing files:")
        for name in data["missing_files"]:
            print(f"  - {name}")
    if data["warnings"]:
        print("Warnings:")
        for warning in data["warnings"]:
            print(f"  - {warning}")
    if data["errors"]:
        print("Errors:")
        for error in data["errors"]:
            print(f"  - {error}")
    print(f"Status: {'ok' if data['ok'] else 'failed'}")


def print_discovery_report(data: dict[str, Any]) -> None:
    print(f"Output directory: {data['output_dir']}")
    print(f"JSON catalogs: {len(data['files'])}")
    if data["files"]:
        print("Catalogs:")
        for file in data["files"]:
            count = file["entry_count"] if file["entry_count"] is not None else "unknown"
            status = "readable" if file["readable"] else "unreadable"
            print(f"  - {file['relative_path']} [{file['role']}, {status}, {count} entries]")
            for warning in file["warnings"]:
                print(f"    Warning: {warning}")
            for error in file["errors"]:
                print(f"    Error: {error}")
    if data["recommended_english"] and data["recommended_chinese"]:
        print("Recommended merge inputs:")
        print(f"  English: {data['recommended_english']}")
        print(f"  Chinese: {data['recommended_chinese']}")
    if data["warnings"]:
        print("Warnings:")
        for warning in data["warnings"]:
            print(f"  - {warning}")
    if data["errors"]:
        print("Errors:")
        for error in data["errors"]:
            print(f"  - {error}")
    print(f"Status: {'ok' if data['ok'] else 'failed'}")


def print_extraction_result(data: dict[str, Any]) -> None:
    plan = data["plan"] if "plan" in data else data
    print(f"Game directory: {plan['game_dir']}")
    print(f"Output directory: {plan['output_dir']}")
    print(f"Mode: {'dry-run' if plan['dry_run'] else 'extract'}")
    print(f"Command: {plan['command_text']}")
    if plan["warnings"]:
        print("Warnings:")
        for warning in plan["warnings"]:
            print(f"  - {warning}")
    if plan["errors"]:
        print("Errors:")
        for error in plan["errors"]:
            print(f"  - {error}")
    if "returncode" in data and data["returncode"] is not None:
        print(f"Return code: {data['returncode']}")
        if data["stdout"]:
            print("Stdout:")
            print(data["stdout"].rstrip())
        if data["stderr"]:
            print("Stderr:")
            print(data["stderr"].rstrip())
    print(f"Status: {'ok' if data['ok'] else 'failed'}")


def add_game_dir_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--game-dir", required=True, type=Path, help="Detroit: Become Human install directory.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dbh-bisub", description="Local DBH bilingual subtitle patcher.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="Inspect a game directory.")
    add_game_dir_argument(verify)
    verify.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    verify.add_argument("--hashes", action="store_true", help="Include SHA-256 hashes for detected game files.")

    patch = subparsers.add_parser("patch", help="Create or apply a patch plan.")
    add_game_dir_argument(patch)
    patch.add_argument("--dry-run", action="store_true", help="Inspect planned writes without modifying game files.")
    patch.add_argument("--force", action="store_true", help="Allow planning over an existing patch archive.")
    patch.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    backup = subparsers.add_parser("backup", help="Back up files this tool may modify.")
    add_game_dir_argument(backup)
    backup.add_argument("--file", action="append", dest="files", help="Relative game file to back up. May be repeated.")
    backup.add_argument("--backup-id", help="Backup id. Defaults to a UTC timestamp.")
    backup.add_argument("--dry-run", action="store_true", help="Show the backup plan without copying files.")
    backup.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    restore = subparsers.add_parser("restore", help="Restore a backup created by this tool.")
    add_game_dir_argument(restore)
    restore.add_argument("--backup-id", default="latest", help="Backup id to restore. Defaults to latest.")
    restore.add_argument("--dry-run", action="store_true", help="Show which backup would be restored.")
    restore.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    tools = subparsers.add_parser("tools", help="Inspect external DBH helper tools.")
    tools.add_argument("--file-parser", type=Path, help="Path to FileParser executable.")
    tools.add_argument("--idx-detroit", type=Path, help="Path to IDX_Detroit executable.")
    tools.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    tools.add_argument("--examples", action="store_true", help="Print example extract/repack commands.")
    tools.add_argument("--game-dir", type=Path, help="Game directory for example commands.")
    tools.add_argument("--output-dir", type=Path, help="FileParser output directory for example commands.")
    tools.add_argument("--archive-id", type=int, default=1, help="IDX-Detroit archive id for extract examples.")
    tools.add_argument("--object-count", type=int, default=0, help="IDX-Detroit object count; 0 means all.")
    tools.add_argument("--file-size-table", type=Path, help="FileSizeTable path for repack examples.")
    tools.add_argument("--verbose-example", action="store_true", help="Include FileParser verbose flag in examples.")

    extract = subparsers.add_parser("extract", help="Run FileParser against a local DBH game directory.")
    add_game_dir_argument(extract)
    extract.add_argument("--output-dir", required=True, type=Path, help="FileParser output directory.")
    extract.add_argument("--file-parser", type=Path, help="Path to FileParser executable.")
    extract.add_argument("--dry-run", action="store_true", help="Print the extraction plan without running FileParser.")
    extract.add_argument("--force", action="store_true", help="Allow using a non-empty output directory.")
    extract.add_argument("--verbose-tool", action="store_true", help="Pass FileParser verbose flag.")
    extract.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    discover = subparsers.add_parser("discover", help="Discover language JSON catalogs in a FileParser output directory.")
    discover.add_argument("--output-dir", required=True, type=Path, help="FileParser output directory.")
    discover.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    merge = subparsers.add_parser("merge", help="Merge English and Chinese text catalogs into bilingual text.")
    merge.add_argument("--english", required=True, type=Path, help="English catalog JSON.")
    merge.add_argument("--chinese", required=True, type=Path, help="Chinese catalog JSON.")
    merge.add_argument("--output", required=True, type=Path, help="Output bilingual catalog JSON.")
    merge.add_argument("--report", type=Path, help="Optional JSON merge report path.")
    merge.add_argument("--terms", type=Path, help="Optional terminology CSV applied to Chinese text before merging.")
    merge.add_argument("--json", action="store_true", help="Print machine-readable report JSON.")

    lint = subparsers.add_parser("lint", help="Inspect a merged text catalog for subtitle quality risks.")
    lint.add_argument("--catalog", required=True, type=Path, help="Catalog JSON to inspect.")
    lint.add_argument("--report", type=Path, help="Optional JSON quality report path.")
    lint.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES, help="Maximum visual lines per entry.")
    lint.add_argument(
        "--max-line-chars",
        type=int,
        default=DEFAULT_MAX_LINE_CHARS,
        help="Maximum characters in one visual line.",
    )
    lint.add_argument(
        "--max-total-chars",
        type=int,
        default=DEFAULT_MAX_TOTAL_CHARS,
        help="Maximum total characters across all visual lines.",
    )
    lint.add_argument("--json", action="store_true", help="Print machine-readable report JSON.")

    return parser


def run_verify(args: argparse.Namespace) -> int:
    report = inspect_game_dir(args.game_dir, include_hashes=args.hashes)
    if args.json:
        print_json(report.to_dict())
    else:
        print_verify_report(report)
    return 0 if report.ok else 2


def run_patch(args: argparse.Namespace) -> int:
    plan = build_patch_plan(args.game_dir, dry_run=args.dry_run, force=args.force)
    if args.json:
        print_json(plan.to_dict())
    else:
        print_patch_plan(plan)
    return 0 if plan.can_apply else 2


def run_backup(args: argparse.Namespace) -> int:
    files = args.files or DEFAULT_BACKUP_FILES
    try:
        plan = plan_backup(args.game_dir, files, backup_id=args.backup_id)
        data = plan.to_dict()
        data["dry_run"] = args.dry_run
        if plan.ok and not args.dry_run:
            manifest = create_backup(args.game_dir, files, backup_id=plan.backup_id)
            data["manifest"] = manifest.to_dict()
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print_json(data)
    else:
        print_backup_plan(data, dry_run=args.dry_run)
    return 0 if data["ok"] else 2


def run_restore(args: argparse.Namespace) -> int:
    try:
        manifest = restore_backup(args.game_dir, args.backup_id, dry_run=args.dry_run)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    data = manifest.to_dict()
    data["dry_run"] = args.dry_run
    if args.json:
        print_json(data)
    else:
        action = "Would restore" if args.dry_run else "Restored"
        print(f"{action} backup: {manifest.backup_id}")
        for entry in manifest.files:
            print(f"  - {entry.source}")
    return 0


def run_tools(args: argparse.Namespace) -> int:
    report = inspect_toolchain(file_parser=args.file_parser, idx_detroit=args.idx_detroit)
    if args.json:
        print_json(report.to_dict())
    else:
        print_toolchain_report(report)
        if args.examples:
            print()
            print_tool_examples(args)
    return 0 if report.ok else 2


def run_discover(args: argparse.Namespace) -> int:
    report = discover_catalogs(args.output_dir)
    data = report.to_dict()
    if args.json:
        print_json(data)
    else:
        print_discovery_report(data)
    return 0 if report.ok else 2


def run_extract(args: argparse.Namespace) -> int:
    plan = plan_extraction(
        args.game_dir,
        args.output_dir,
        file_parser=args.file_parser,
        dry_run=args.dry_run,
        force=args.force,
        verbose=args.verbose_tool,
    )
    result = run_extraction(plan)
    data = result.to_dict()
    if args.json:
        print_json(data)
    else:
        print_extraction_result(data)
    return 0 if result.ok else 2


def run_merge(args: argparse.Namespace) -> int:
    try:
        english = load_catalog(args.english)
        chinese = load_catalog(args.chinese)
        terminology_report = None
        if args.terms:
            rules = load_terminology(args.terms)
            chinese, terminology_report = apply_terminology_to_catalog(chinese, rules)
        result = merge_catalogs(english, chinese)
        save_catalog(args.output, result.catalog)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    report_data = result.report.to_dict()
    if terminology_report:
        report_data["terminology"] = terminology_report.to_dict()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print_json(report_data)
    else:
        print_merge_report(report_data, args.output, args.report)
    return 0 if result.report.ok else 2


def run_lint(args: argparse.Namespace) -> int:
    try:
        catalog = load_catalog(args.catalog)
        report = inspect_catalog_quality(
            catalog,
            max_lines=args.max_lines,
            max_line_chars=args.max_line_chars,
            max_total_chars=args.max_total_chars,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    report_data = report.to_dict()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print_json(report_data)
    else:
        print_quality_report(report_data, args.report)
    return 0 if report.ok else 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "verify":
        return run_verify(args)
    if args.command == "patch":
        return run_patch(args)
    if args.command == "backup":
        return run_backup(args)
    if args.command == "restore":
        return run_restore(args)
    if args.command == "tools":
        return run_tools(args)
    if args.command == "extract":
        return run_extract(args)
    if args.command == "discover":
        return run_discover(args)
    if args.command == "merge":
        return run_merge(args)
    if args.command == "lint":
        return run_lint(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
