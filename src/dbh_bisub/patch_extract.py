from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any

from .idx_archive import default_idx_file, plan_idx_extract
from .prepare import EXTRACTED_DIR, REPORTS_DIR

PATCH_EXTRACT_RESULT_JSON = "patch-extract-result.json"


@dataclass(frozen=True)
class PatchExtractResult:
    ok: bool
    execute: bool
    game_dir: str
    work_dir: str
    extracted_dir: str
    idx_file: str
    report_path: str | None
    idx_extract: dict[str, Any] | None
    returncode: int | None
    stdout: str
    stderr: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_patch_workdir(
    game_dir: Path | str,
    work_dir: Path | str,
    *,
    idx_file: Path | str | None = None,
    idx_detroit: Path | str | None = None,
    archive_id: int = 1,
    object_count: int = 0,
    execute: bool = False,
    force: bool = False,
    report: Path | str | None = None,
) -> PatchExtractResult:
    game_root = Path(game_dir)
    work_root = Path(work_dir)
    extracted_dir = work_root / EXTRACTED_DIR
    idx_path = Path(idx_file) if idx_file is not None else default_idx_file(game_root)
    report_path = _resolve_report(work_root, report)
    errors: list[str] = []
    warnings: list[str] = []

    if not work_root.exists() or not work_root.is_dir():
        errors.append(f"Work directory does not exist: {work_root}")
    elif extracted_dir.exists() and not extracted_dir.is_dir():
        errors.append(f"Extracted path is not a directory: {extracted_dir}")
    elif extracted_dir.exists() and any(extracted_dir.iterdir()) and not force:
        errors.append(f"Extracted directory is not empty: {extracted_dir}. Use --force to reuse it.")

    plan = plan_idx_extract(
        idx_path,
        idx_detroit=idx_detroit,
        archive_id=archive_id,
        object_count=object_count,
        dry_run=not execute,
    )
    plan_data = plan.to_dict()
    errors.extend(plan.errors)
    warnings.extend(plan.warnings)

    returncode: int | None = None
    stdout = ""
    stderr = ""
    if not errors and execute:
        extracted_dir.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                plan.command,
                check=False,
                capture_output=True,
                text=True,
                cwd=extracted_dir,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except OSError as exc:
            returncode = -1
            stderr = str(exc)
        if returncode != 0:
            errors.append("IDX-Detroit extract failed.")

    result = PatchExtractResult(
        ok=not errors,
        execute=execute,
        game_dir=str(game_root),
        work_dir=str(work_root),
        extracted_dir=str(extracted_dir),
        idx_file=str(idx_path),
        report_path=str(report_path) if report_path is not None else None,
        idx_extract=plan_data,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        errors=errors,
        warnings=warnings,
    )
    if report is not None:
        save_patch_extract_result(report_path, result)
    return result


def save_patch_extract_result(path: Path | str, result: PatchExtractResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_report(root: Path, report: Path | str | None) -> Path | None:
    if report is None:
        return root / REPORTS_DIR / PATCH_EXTRACT_RESULT_JSON
    return Path(report)
