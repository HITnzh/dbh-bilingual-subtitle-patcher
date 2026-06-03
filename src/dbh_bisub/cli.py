from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .backup_restore import restore_backup
from .game_files import GameDirectoryReport, inspect_game_dir
from .patcher import PatchPlan, build_patch_plan


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

    restore = subparsers.add_parser("restore", help="Restore a backup created by this tool.")
    add_game_dir_argument(restore)
    restore.add_argument("--backup-id", default="latest", help="Backup id to restore. Defaults to latest.")
    restore.add_argument("--dry-run", action="store_true", help="Show which backup would be restored.")
    restore.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "verify":
        return run_verify(args)
    if args.command == "patch":
        return run_patch(args)
    if args.command == "restore":
        return run_restore(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
