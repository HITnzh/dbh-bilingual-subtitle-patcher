from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .backup_restore import DEFAULT_BACKUP_FILES, plan_backup
from .catalog import load_catalog
from .constants import INDEX_FILE, PATCH_ARCHIVE
from .game_files import GameDirectoryReport, inspect_game_dir
from .hash_manifest import compare_hash_manifest, load_hash_manifest
from .toolchain import IDX_DETROIT, FILE_PARSER, probe_tool


@dataclass(frozen=True)
class PatchStep:
    id: str
    description: str
    status: str
    details: dict[str, Any]


@dataclass(frozen=True)
class PatchPlan:
    game_dir: str
    dry_run: bool
    can_apply: bool
    catalog: str | None
    catalog_entries: int | None
    work_dir: str | None
    hash_manifest: str | None
    hash_report: dict[str, Any] | None
    backup_plan: dict[str, Any] | None
    toolchain: dict[str, Any]
    steps: list[PatchStep]
    planned_writes: list[str]
    required_backups: list[str]
    errors: list[str]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_dir": self.game_dir,
            "dry_run": self.dry_run,
            "can_apply": self.can_apply,
            "catalog": self.catalog,
            "catalog_entries": self.catalog_entries,
            "work_dir": self.work_dir,
            "hash_manifest": self.hash_manifest,
            "hash_report": self.hash_report,
            "backup_plan": self.backup_plan,
            "toolchain": self.toolchain,
            "steps": [asdict(step) for step in self.steps],
            "planned_writes": self.planned_writes,
            "required_backups": self.required_backups,
            "errors": self.errors,
            "warnings": self.warnings,
            "notes": self.notes,
        }


def build_patch_plan(
    game_dir: Path | str,
    *,
    dry_run: bool = True,
    force: bool = False,
    catalog: Path | str | None = None,
    work_dir: Path | str | None = None,
    hash_manifest: Path | str | None = None,
    require_hash: bool = False,
    file_parser: Path | str | None = None,
    idx_detroit: Path | str | None = None,
) -> PatchPlan:
    root = Path(game_dir)
    report: GameDirectoryReport = inspect_game_dir(game_dir)
    errors = list(report.errors)
    warnings = list(report.warnings)
    notes = [
        "Real patch writing is not implemented yet.",
        "This plan validates inputs, safety checks, tool availability, and planned writes.",
    ]
    steps: list[PatchStep] = []
    hash_report: dict[str, Any] | None = None
    backup_plan: dict[str, Any] | None = None
    catalog_entries: int | None = None
    toolchain: dict[str, Any] = {}

    if not dry_run:
        errors.append("Real patch application is not implemented yet. Use --dry-run for now.")

    if report.patch_archive.exists and not force:
        errors.append(f"{PATCH_ARCHIVE} already exists. Re-run with --force after checking mod compatibility.")

    if catalog is not None:
        catalog_path = Path(catalog)
        try:
            loaded_catalog = load_catalog(catalog_path)
            catalog_entries = loaded_catalog.count
            if loaded_catalog.count == 0:
                warnings.append(f"Bilingual catalog contains no entries: {catalog_path}")
            steps.append(
                PatchStep(
                    "load_catalog",
                    "Load bilingual catalog.",
                    "ready",
                    {"path": str(catalog_path), "entries": loaded_catalog.count},
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"Failed to load bilingual catalog: {exc}")
            steps.append(
                PatchStep(
                    "load_catalog",
                    "Load bilingual catalog.",
                    "blocked",
                    {"path": str(catalog_path), "error": str(exc)},
                )
            )
    else:
        notes.append("No bilingual catalog was provided; pass --catalog before real patch application.")
        steps.append(PatchStep("load_catalog", "Load bilingual catalog.", "pending", {}))

    work_path = Path(work_dir) if work_dir is not None else None
    if work_path is not None:
        if work_path.exists() and not work_path.is_dir():
            errors.append(f"Work path is not a directory: {work_path}")
            status = "blocked"
        else:
            status = "ready" if work_path.exists() else "planned"
        steps.append(
            PatchStep(
                "prepare_work_dir",
                "Prepare patch work directory.",
                status,
                {"path": str(work_path), "exists": work_path.exists()},
            )
        )
    else:
        notes.append("No work directory was provided; pass --work-dir for real patch application.")
        steps.append(PatchStep("prepare_work_dir", "Prepare patch work directory.", "pending", {}))

    if hash_manifest is not None:
        manifest_path = Path(hash_manifest)
        try:
            manifest = load_hash_manifest(manifest_path)
            comparison = compare_hash_manifest(root, manifest)
            hash_report = comparison.to_dict()
            if not comparison.ok:
                errors.append(f"Game files do not match hash manifest: {manifest_path}")
            steps.append(
                PatchStep(
                    "verify_hashes",
                    "Compare game files against hash manifest.",
                    "ready" if comparison.ok else "blocked",
                    {"manifest": str(manifest_path), "report": hash_report},
                )
            )
        except (OSError, ValueError) as exc:
            errors.append(f"Failed to compare hash manifest: {exc}")
            steps.append(
                PatchStep(
                    "verify_hashes",
                    "Compare game files against hash manifest.",
                    "blocked",
                    {"manifest": str(manifest_path), "error": str(exc)},
                )
            )
    elif require_hash:
        errors.append("A hash manifest is required. Pass --hash-manifest or remove --require-hash.")
        steps.append(PatchStep("verify_hashes", "Compare game files against hash manifest.", "blocked", {}))
    else:
        warnings.append("No hash manifest was provided; patch apply should verify hashes before writing.")
        steps.append(PatchStep("verify_hashes", "Compare game files against hash manifest.", "pending", {}))

    backup = plan_backup(root, DEFAULT_BACKUP_FILES)
    backup_plan = backup.to_dict()
    if not backup.ok:
        errors.extend(f"Backup plan failed: {message}" for message in backup.errors)
        backup_status = "blocked"
    else:
        backup_status = "ready"
    steps.append(
        PatchStep(
            "create_backup",
            "Create safety backup before writing game files.",
            backup_status,
            backup_plan,
        )
    )

    for spec, explicit in ((FILE_PARSER, file_parser), (IDX_DETROIT, idx_detroit)):
        probe = probe_tool(spec, explicit)
        toolchain[spec.id] = probe.to_dict()
        if explicit is not None and not probe.available:
            errors.extend(f"{spec.display_name}: {message}" for message in probe.errors)
        elif spec.id == IDX_DETROIT.id and not probe.available:
            warnings.append(f"{spec.display_name} was not found; pass its path before real patch application.")

    steps.append(
        PatchStep(
            "extract_archive",
            "Use IDX-Detroit to extract archive data into the work directory.",
            "planned" if toolchain.get(IDX_DETROIT.id, {}).get("available") else "pending",
            {"tool": "idx_detroit"},
        )
    )
    steps.append(
        PatchStep(
            "inject_catalog",
            "Inject bilingual catalog into extracted localization data.",
            "planned" if catalog_entries is not None else "pending",
            {"catalog_entries": catalog_entries},
        )
    )
    steps.append(
        PatchStep(
            "repack_archive",
            "Use IDX-Detroit to repack BigFile_PC.idx and the patch archive slot.",
            "planned" if toolchain.get(IDX_DETROIT.id, {}).get("available") else "pending",
            {"planned_outputs": [INDEX_FILE, PATCH_ARCHIVE]},
        )
    )

    planned_writes = [INDEX_FILE, PATCH_ARCHIVE] if report.ok else []
    required_backups = [name for name in planned_writes if name == INDEX_FILE or report.patch_archive.exists]
    if PATCH_ARCHIVE not in required_backups and report.patch_archive.exists:
        required_backups.append(PATCH_ARCHIVE)

    return PatchPlan(
        game_dir=str(root),
        dry_run=dry_run,
        can_apply=not errors and dry_run,
        catalog=str(catalog) if catalog is not None else None,
        catalog_entries=catalog_entries,
        work_dir=str(work_path) if work_path is not None else None,
        hash_manifest=str(hash_manifest) if hash_manifest is not None else None,
        hash_report=hash_report,
        backup_plan=backup_plan,
        toolchain=toolchain,
        steps=steps,
        planned_writes=planned_writes,
        required_backups=required_backups,
        errors=errors,
        warnings=warnings,
        notes=notes,
    )
