from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .backup_restore import DEFAULT_BACKUP_FILES, plan_backup
from .patch_inject import patch_inject_workdir
from .patch_package import package_patch_workdir


@dataclass(frozen=True)
class StageStep:
    id: str
    description: str
    status: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchStageResult:
    ok: bool
    game_dir: str
    work_dir: str
    backup_plan: dict[str, Any] | None
    injection: dict[str, Any] | None
    package: dict[str, Any] | None
    steps: list[StageStep]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "game_dir": self.game_dir,
            "work_dir": self.work_dir,
            "backup_plan": self.backup_plan,
            "injection": self.injection,
            "package": self.package,
            "steps": [step.to_dict() for step in self.steps],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def stage_patch_workdir(
    game_dir: Path | str,
    work_dir: Path | str,
    *,
    source: Path | str | None = None,
    target: Path | str | None = None,
    output: Path | str | None = None,
    inject_report: Path | str | None = None,
    text_field: str | None = None,
    idx_dat_language: str | None = None,
    package_dir: Path | str | None = None,
    package_manifest: Path | str | None = None,
    idx_file: Path | str | None = None,
    file_size_table: Path | str | None = None,
    idx_detroit: Path | str | None = None,
    require_repack_plan: bool = False,
) -> PatchStageResult:
    game_root = Path(game_dir)
    work_root = Path(work_dir)
    errors: list[str] = []
    warnings: list[str] = []
    steps: list[StageStep] = []

    backup_plan = plan_backup(game_root, DEFAULT_BACKUP_FILES)
    backup_data = backup_plan.to_dict()
    warnings.extend(backup_plan.warnings)
    if backup_plan.ok:
        steps.append(StageStep("backup_preflight", "Plan safety backup.", "ready", backup_data))
    else:
        errors.extend(f"Backup preflight failed: {message}" for message in backup_plan.errors)
        steps.append(StageStep("backup_preflight", "Plan safety backup.", "blocked", backup_data))
        return _result(game_root, work_root, backup_data, None, None, steps, errors, warnings)

    injection = patch_inject_workdir(
        work_root,
        source=source,
        target=target,
        output=output,
        report=inject_report,
        text_field=text_field,
        idx_dat_language=idx_dat_language,
    )
    injection_data = injection.to_dict()
    warnings.extend(injection.warnings)
    if injection.ok:
        steps.append(StageStep("inject_catalog", "Inject bilingual catalog into extracted data.", "done", injection_data))
    else:
        errors.extend(f"Catalog injection failed: {message}" for message in injection.errors)
        steps.append(StageStep("inject_catalog", "Inject bilingual catalog into extracted data.", "blocked", injection_data))
        return _result(game_root, work_root, backup_data, injection_data, None, steps, errors, warnings)

    packaged = package_patch_workdir(
        work_root,
        package_dir=package_dir,
        manifest=package_manifest,
        game_dir=game_root,
        idx_file=idx_file,
        file_size_table=file_size_table,
        idx_detroit=idx_detroit,
    )
    package_data = packaged.to_dict()
    warnings.extend(packaged.warnings)
    if packaged.ok:
        steps.append(StageStep("package_patch", "Package generated files and plan repack.", "done", package_data))
    else:
        errors.extend(f"Patch package failed: {message}" for message in packaged.errors)
        steps.append(StageStep("package_patch", "Package generated files and plan repack.", "blocked", package_data))
        return _result(game_root, work_root, backup_data, injection_data, package_data, steps, errors, warnings)

    repack_plan = package_data.get("repack_plan")
    if require_repack_plan and not _repack_plan_ok(repack_plan):
        errors.append("A successful repack dry-run plan is required; pass IDX-Detroit, BigFile_PC.idx, and FileSizeTable inputs.")
        steps.append(StageStep("repack_preflight", "Require successful repack dry-run plan.", "blocked", {"repack_plan": repack_plan}))
    else:
        status = "ready" if _repack_plan_ok(repack_plan) else "pending"
        steps.append(StageStep("repack_preflight", "Review repack dry-run plan.", status, {"repack_plan": repack_plan}))

    return _result(game_root, work_root, backup_data, injection_data, package_data, steps, errors, warnings)


def save_patch_stage_result(path: Path | str, result: PatchStageResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _result(
    game_dir: Path,
    work_dir: Path,
    backup_plan: dict[str, Any] | None,
    injection: dict[str, Any] | None,
    package: dict[str, Any] | None,
    steps: list[StageStep],
    errors: list[str],
    warnings: list[str],
) -> PatchStageResult:
    return PatchStageResult(
        ok=not errors,
        game_dir=str(game_dir),
        work_dir=str(work_dir),
        backup_plan=backup_plan,
        injection=injection,
        package=package,
        steps=steps,
        errors=errors,
        warnings=warnings,
    )


def _repack_plan_ok(repack_plan: Any) -> bool:
    return isinstance(repack_plan, dict) and bool(repack_plan.get("ok"))
