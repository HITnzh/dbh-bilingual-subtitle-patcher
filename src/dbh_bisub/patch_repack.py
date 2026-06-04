from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .backup_restore import DEFAULT_BACKUP_FILES, create_backup, plan_backup
from .constants import PATCH_ARCHIVE
from .hash_manifest import compare_hash_manifest, load_hash_manifest
from .idx_archive import default_idx_file, plan_idx_repack, run_idx_plan
from .patch_materialize import MATERIALIZE_MANIFEST_JSON
from .patch_package import PACKAGE_MANIFEST_JSON
from .prepare import REPORTS_DIR


@dataclass(frozen=True)
class RepackStep:
    id: str
    description: str
    status: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchRepackResult:
    ok: bool
    execute: bool
    game_dir: str
    work_dir: str
    idx_file: str
    file_size_table: str | None
    materialize_manifest: str | None
    hash_report: dict[str, Any] | None
    backup_plan: dict[str, Any] | None
    backup_manifest: dict[str, Any] | None
    repack: dict[str, Any] | None
    steps: list[RepackStep]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "execute": self.execute,
            "game_dir": self.game_dir,
            "work_dir": self.work_dir,
            "idx_file": self.idx_file,
            "file_size_table": self.file_size_table,
            "materialize_manifest": self.materialize_manifest,
            "hash_report": self.hash_report,
            "backup_plan": self.backup_plan,
            "backup_manifest": self.backup_manifest,
            "repack": self.repack,
            "steps": [step.to_dict() for step in self.steps],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def repack_patch_workdir(
    game_dir: Path | str,
    work_dir: Path | str,
    *,
    idx_file: Path | str | None = None,
    file_size_table: Path | str | None = None,
    materialize_manifest: Path | str | None = None,
    hash_manifest: Path | str | None = None,
    idx_detroit: Path | str | None = None,
    backup_id: str | None = None,
    execute: bool = False,
    allow_unmaterialized: bool = False,
    require_hash: bool = False,
    allow_unverified_execute: bool = False,
) -> PatchRepackResult:
    game_root = Path(game_dir)
    work_root = Path(work_dir)
    idx_path = Path(idx_file) if idx_file is not None else default_idx_file(game_root)
    errors: list[str] = []
    warnings: list[str] = []
    steps: list[RepackStep] = []
    hash_report: dict[str, Any] | None = None

    materialize_path = _resolve_materialize_manifest(work_root, materialize_manifest)
    materialize_data = _load_materialize_manifest(materialize_path, errors, warnings, allow_unmaterialized=allow_unmaterialized)
    if materialize_data is not None:
        steps.append(
            RepackStep(
                "materialize_check",
                "Verify materialized patch files.",
                "ready",
                {"manifest": str(materialize_path), "files": len(materialize_data.get("files", []))},
            )
        )
    elif allow_unmaterialized:
        steps.append(
            RepackStep(
                "materialize_check",
                "Verify materialized patch files.",
                "skipped",
                {"manifest": str(materialize_path)},
            )
        )
    else:
        steps.append(
            RepackStep(
                "materialize_check",
                "Verify materialized patch files.",
                "blocked",
                {"manifest": str(materialize_path)},
            )
        )

    if hash_manifest is not None:
        manifest_path = Path(hash_manifest)
        try:
            manifest = load_hash_manifest(manifest_path)
            comparison = compare_hash_manifest(game_root, manifest)
            hash_report = comparison.to_dict()
            if comparison.ok:
                steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "ready", {"manifest": str(manifest_path), "report": hash_report}))
            else:
                errors.append(f"Game files do not match hash manifest: {manifest_path}")
                steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "blocked", {"manifest": str(manifest_path), "report": hash_report}))
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
            errors.append(f"Failed to compare hash manifest: {exc}")
            steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "blocked", {"manifest": str(manifest_path), "error": str(exc)}))
    elif execute and not allow_unverified_execute:
        errors.append("A hash manifest is required before executing repack. Pass --hash-manifest or --allow-unverified-execute.")
        steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "blocked", {}))
    elif require_hash:
        errors.append("A hash manifest is required. Pass --hash-manifest or remove --require-hash.")
        steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "blocked", {}))
    else:
        warnings.append("No hash manifest was provided; repack execution should verify hashes before writing.")
        steps.append(RepackStep("verify_hashes", "Compare game files against hash manifest.", "pending", {}))

    table_path, table_warnings = _resolve_file_size_table(work_root, file_size_table)
    warnings.extend(table_warnings)
    if table_path is None:
        errors.append("FileSizeTable is required for repack planning.")
        steps.append(RepackStep("resolve_file_size_table", "Resolve FileSizeTable.", "blocked", {}))
    else:
        steps.append(RepackStep("resolve_file_size_table", "Resolve FileSizeTable.", "ready", {"path": str(table_path)}))

    backup_plan_data: dict[str, Any] | None = None
    backup_manifest_data: dict[str, Any] | None = None
    backup = plan_backup(game_root, DEFAULT_BACKUP_FILES, backup_id=backup_id)
    backup_plan_data = backup.to_dict()
    warnings.extend(backup.warnings)
    if backup.ok:
        steps.append(RepackStep("backup_plan", "Plan safety backup.", "ready", backup_plan_data))
    else:
        errors.extend(f"Backup plan failed: {message}" for message in backup.errors)
        steps.append(RepackStep("backup_plan", "Plan safety backup.", "blocked", backup_plan_data))

    repack_data: dict[str, Any] | None = None
    if table_path is not None:
        plan = plan_idx_repack(idx_path, table_path, idx_detroit=idx_detroit, dry_run=not execute)
        if not plan.ok:
            errors.extend(f"Repack plan failed: {message}" for message in plan.errors)
            steps.append(RepackStep("repack_plan", "Plan IDX-Detroit repack.", "blocked", plan.to_dict()))
        else:
            steps.append(RepackStep("repack_plan", "Plan IDX-Detroit repack.", "ready", plan.to_dict()))
        if not errors:
            if execute:
                manifest = create_backup(game_root, DEFAULT_BACKUP_FILES, backup_id=backup.backup_id)
                backup_manifest_data = manifest.to_dict()
                steps.append(RepackStep("create_backup", "Create safety backup.", "done", backup_manifest_data))
            result = run_idx_plan(plan)
            repack_data = result.to_dict()
            status = "done" if result.ok and execute else "ready" if result.ok else "blocked"
            if not result.ok:
                errors.append("IDX-Detroit repack failed.")
            steps.append(RepackStep("run_repack", "Run IDX-Detroit repack." if execute else "Review IDX-Detroit repack dry-run.", status, repack_data))
            if result.ok and execute and table_path is not None:
                install_data, install_errors = _install_patch_archive(game_root, table_path)
                if install_errors:
                    errors.extend(install_errors)
                    steps.append(RepackStep("install_patch_archive", "Install repacked patch archive.", "blocked", install_data))
                else:
                    steps.append(RepackStep("install_patch_archive", "Install repacked patch archive.", "done", install_data))

    return PatchRepackResult(
        ok=not errors,
        execute=execute,
        game_dir=str(game_root),
        work_dir=str(work_root),
        idx_file=str(idx_path),
        file_size_table=str(table_path) if table_path is not None else None,
        materialize_manifest=str(materialize_path) if materialize_path is not None else None,
        hash_report=hash_report,
        backup_plan=backup_plan_data,
        backup_manifest=backup_manifest_data,
        repack=repack_data,
        steps=steps,
        errors=errors,
        warnings=warnings,
    )


def save_patch_repack_result(path: Path | str, result: PatchRepackResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_materialize_manifest(root: Path, materialize_manifest: Path | str | None) -> Path:
    if materialize_manifest is None:
        return root / REPORTS_DIR / MATERIALIZE_MANIFEST_JSON
    return _resolve_path(root, materialize_manifest)


def _load_materialize_manifest(
    path: Path,
    errors: list[str],
    warnings: list[str],
    *,
    allow_unmaterialized: bool,
) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        message = f"Materialize manifest does not exist: {path}"
        if allow_unmaterialized:
            warnings.append(message)
        else:
            errors.append(message)
        return None
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not data.get("ok"):
        errors.append(f"Materialize manifest is not ok: {path}")
        return data
    files = data.get("files")
    if not isinstance(files, list) or not files:
        errors.append(f"Materialize manifest contains no files: {path}")
        return data
    return data


def _resolve_file_size_table(root: Path, file_size_table: Path | str | None) -> tuple[Path | None, list[str]]:
    if file_size_table is not None:
        candidate = _resolve_path(root, file_size_table)
        if not candidate.exists() or not candidate.is_file():
            return None, [f"FileSizeTable does not exist: {candidate}"]
        return candidate, []

    package_manifest = root / REPORTS_DIR / PACKAGE_MANIFEST_JSON
    if package_manifest.exists() and package_manifest.is_file():
        try:
            data = json.loads(package_manifest.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            data = {}
        table = data.get("file_size_table")
        if isinstance(table, str) and table:
            candidate = Path(table)
            if candidate.exists() and candidate.is_file():
                return candidate, []

    candidates = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.name.lower().endswith(".filesizetable")
    ]
    candidates = sorted(candidates, key=lambda path: str(path).lower())
    if len(candidates) == 1:
        return candidates[0], []
    if not candidates:
        return None, ["No FileSizeTable was found."]
    return None, ["Multiple FileSizeTable files were found; pass --file-size-table explicitly."]


def _resolve_path(root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return root / candidate


def _install_patch_archive(game_dir: Path, file_size_table: Path) -> tuple[dict[str, Any], list[str]]:
    source = file_size_table.parent / PATCH_ARCHIVE
    target = game_dir / PATCH_ARCHIVE
    data: dict[str, Any] = {
        "source": str(source),
        "target": str(target),
    }
    errors: list[str] = []
    if not source.exists() or not source.is_file():
        errors.append(f"Repacked patch archive was not created: {source}")
        return data, errors
    try:
        _assert_inside(game_dir, target)
    except ValueError as exc:
        errors.append(str(exc))
        return data, errors

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    data.update(
        {
            "size": target.stat().st_size,
            "sha256": _sha256(target),
        }
    )
    return data, errors


def _assert_inside(root: Path, target: Path) -> None:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
        raise ValueError(f"Refusing to install outside game directory: {target}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
