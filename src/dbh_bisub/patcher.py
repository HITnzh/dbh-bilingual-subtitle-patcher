from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .constants import INDEX_FILE, PATCH_ARCHIVE
from .game_files import GameDirectoryReport, inspect_game_dir


@dataclass(frozen=True)
class PatchPlan:
    game_dir: str
    dry_run: bool
    can_apply: bool
    planned_writes: list[str]
    required_backups: list[str]
    errors: list[str]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_patch_plan(game_dir: Path | str, *, dry_run: bool = True, force: bool = False) -> PatchPlan:
    report: GameDirectoryReport = inspect_game_dir(game_dir)
    errors = list(report.errors)
    warnings = list(report.warnings)
    notes = [
        "DBH extractor/packer integration is not implemented yet.",
        "This dry-run only validates the game directory and planned safety steps.",
    ]

    if not dry_run:
        errors.append("Real patch application is not implemented yet. Use --dry-run for now.")

    if report.patch_archive.exists and not force:
        errors.append(f"{PATCH_ARCHIVE} already exists. Re-run with --force after checking mod compatibility.")

    planned_writes = [INDEX_FILE, PATCH_ARCHIVE] if report.ok else []
    required_backups = [name for name in planned_writes if name == INDEX_FILE or report.patch_archive.exists]

    return PatchPlan(
        game_dir=str(Path(game_dir)),
        dry_run=dry_run,
        can_apply=not errors and dry_run,
        planned_writes=planned_writes,
        required_backups=required_backups,
        errors=errors,
        warnings=warnings,
        notes=notes,
    )
