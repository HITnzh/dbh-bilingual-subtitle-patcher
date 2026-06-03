from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .patch_materialize import materialize_patch_package
from .patch_repack import repack_patch_workdir
from .patch_stage import stage_patch_workdir


@dataclass(frozen=True)
class ApplyStep:
    id: str
    description: str
    status: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchApplyResult:
    ok: bool
    execute_repack: bool
    game_dir: str
    work_dir: str
    stage: dict[str, Any] | None
    materialize: dict[str, Any] | None
    repack: dict[str, Any] | None
    steps: list[ApplyStep]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "execute_repack": self.execute_repack,
            "game_dir": self.game_dir,
            "work_dir": self.work_dir,
            "stage": self.stage,
            "materialize": self.materialize,
            "repack": self.repack,
            "steps": [step.to_dict() for step in self.steps],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def apply_patch_workflow(
    game_dir: Path | str,
    work_dir: Path | str,
    *,
    source: Path | str | None = None,
    target: Path | str | None = None,
    output: Path | str | None = None,
    inject_report: Path | str | None = None,
    text_field: str | None = None,
    package_dir: Path | str | None = None,
    package_manifest: Path | str | None = None,
    materialize_target_dir: Path | str | None = None,
    materialize_manifest: Path | str | None = None,
    idx_file: Path | str | None = None,
    file_size_table: Path | str | None = None,
    idx_detroit: Path | str | None = None,
    backup_id: str | None = None,
    execute_repack: bool = False,
    require_repack_plan: bool = True,
) -> PatchApplyResult:
    game_root = Path(game_dir)
    work_root = Path(work_dir)
    errors: list[str] = []
    warnings: list[str] = []
    steps: list[ApplyStep] = []

    stage = stage_patch_workdir(
        game_root,
        work_root,
        source=source,
        target=target,
        output=output,
        inject_report=inject_report,
        text_field=text_field,
        package_dir=package_dir,
        package_manifest=package_manifest,
        idx_file=idx_file,
        file_size_table=file_size_table,
        idx_detroit=idx_detroit,
        require_repack_plan=require_repack_plan,
    )
    stage_data = stage.to_dict()
    warnings.extend(stage.warnings)
    if not stage.ok:
        errors.extend(f"Patch staging failed: {message}" for message in stage.errors)
        steps.append(ApplyStep("stage", "Run local staging workflow.", "blocked", stage_data))
        return _result(game_root, work_root, execute_repack, stage_data, None, None, steps, errors, warnings)
    steps.append(ApplyStep("stage", "Run local staging workflow.", "done", stage_data))

    materialized = materialize_patch_package(
        work_root,
        package_manifest=package_manifest,
        target_dir=materialize_target_dir,
        manifest=materialize_manifest,
    )
    materialized_data = materialized.to_dict()
    warnings.extend(materialized.warnings)
    if not materialized.ok:
        errors.extend(f"Patch materialize failed: {message}" for message in materialized.errors)
        steps.append(ApplyStep("materialize", "Materialize packaged files into extracted tree.", "blocked", materialized_data))
        return _result(game_root, work_root, execute_repack, stage_data, materialized_data, None, steps, errors, warnings)
    steps.append(ApplyStep("materialize", "Materialize packaged files into extracted tree.", "done", materialized_data))

    repacked = repack_patch_workdir(
        game_root,
        work_root,
        idx_file=idx_file,
        file_size_table=file_size_table,
        materialize_manifest=materialize_manifest,
        idx_detroit=idx_detroit,
        backup_id=backup_id,
        execute=execute_repack,
    )
    repacked_data = repacked.to_dict()
    warnings.extend(repacked.warnings)
    if not repacked.ok:
        errors.extend(f"Patch repack failed: {message}" for message in repacked.errors)
        steps.append(ApplyStep("repack", "Run protected repack workflow.", "blocked", repacked_data))
        return _result(game_root, work_root, execute_repack, stage_data, materialized_data, repacked_data, steps, errors, warnings)
    status = "done" if execute_repack else "ready"
    steps.append(ApplyStep("repack", "Run protected repack workflow.", status, repacked_data))

    return _result(game_root, work_root, execute_repack, stage_data, materialized_data, repacked_data, steps, errors, warnings)


def save_patch_apply_result(path: Path | str, result: PatchApplyResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _result(
    game_dir: Path,
    work_dir: Path,
    execute_repack: bool,
    stage: dict[str, Any] | None,
    materialize: dict[str, Any] | None,
    repack: dict[str, Any] | None,
    steps: list[ApplyStep],
    errors: list[str],
    warnings: list[str],
) -> PatchApplyResult:
    return PatchApplyResult(
        ok=not errors,
        execute_repack=execute_repack,
        game_dir=str(game_dir),
        work_dir=str(work_dir),
        stage=stage,
        materialize=materialize,
        repack=repack,
        steps=steps,
        errors=errors,
        warnings=warnings,
    )
