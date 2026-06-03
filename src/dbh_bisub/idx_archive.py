from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Any, Literal

from .constants import INDEX_FILE
from .toolchain import IDX_DETROIT, build_idx_extract_command, build_idx_repack_command, format_command, probe_tool

IdxAction = Literal["extract", "repack"]


@dataclass(frozen=True)
class IdxPlan:
    action: IdxAction
    idx_file: str
    idx_detroit: str | None
    dry_run: bool
    command: list[str]
    command_text: str
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


@dataclass(frozen=True)
class IdxResult:
    plan: IdxPlan
    returncode: int | None
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.plan.ok and (self.returncode in (None, 0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan": self.plan.to_dict(),
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def default_idx_file(game_dir: Path | str) -> Path:
    return Path(game_dir) / INDEX_FILE


def plan_idx_extract(
    idx_file: Path | str,
    *,
    idx_detroit: Path | str | None = None,
    archive_id: int = 1,
    object_count: int = 0,
    dry_run: bool = True,
) -> IdxPlan:
    idx_path = Path(idx_file)
    errors: list[str] = []
    warnings: list[str] = []

    _validate_idx_file(idx_path, errors)
    _validate_non_negative("archive-id", archive_id, errors)
    _validate_non_negative("object-count", object_count, errors)

    tool = probe_tool(IDX_DETROIT, idx_detroit)
    errors.extend(tool.errors)
    warnings.extend(tool.warnings)
    if not tool.available:
        errors.append("IDX-Detroit is not available. Pass --idx-detroit or add it to PATH.")

    executable = tool.resolved_path or str(idx_detroit or "IDX_Detroit.exe")
    command = build_idx_extract_command(executable, idx_path, archive_id=archive_id, object_count=object_count)
    return IdxPlan(
        action="extract",
        idx_file=str(idx_path),
        idx_detroit=tool.resolved_path,
        dry_run=dry_run,
        command=command,
        command_text=format_command(command),
        errors=errors,
        warnings=warnings,
    )


def plan_idx_repack(
    idx_file: Path | str,
    file_size_table: Path | str,
    *,
    idx_detroit: Path | str | None = None,
    dry_run: bool = True,
) -> IdxPlan:
    idx_path = Path(idx_file)
    table_path = Path(file_size_table)
    errors: list[str] = []
    warnings: list[str] = []

    _validate_idx_file(idx_path, errors)
    if not table_path.exists() or not table_path.is_file():
        errors.append(f"FileSizeTable does not exist: {table_path}")

    tool = probe_tool(IDX_DETROIT, idx_detroit)
    errors.extend(tool.errors)
    warnings.extend(tool.warnings)
    if not tool.available:
        errors.append("IDX-Detroit is not available. Pass --idx-detroit or add it to PATH.")

    executable = tool.resolved_path or str(idx_detroit or "IDX_Detroit.exe")
    command = build_idx_repack_command(executable, idx_path, table_path)
    return IdxPlan(
        action="repack",
        idx_file=str(idx_path),
        idx_detroit=tool.resolved_path,
        dry_run=dry_run,
        command=command,
        command_text=format_command(command),
        errors=errors,
        warnings=warnings,
    )


def run_idx_plan(plan: IdxPlan) -> IdxResult:
    if not plan.ok or plan.dry_run:
        return IdxResult(plan=plan, returncode=None, stdout="", stderr="")

    try:
        completed = subprocess.run(plan.command, check=False, capture_output=True, text=True)
    except OSError as exc:
        return IdxResult(plan=plan, returncode=-1, stdout="", stderr=str(exc))
    return IdxResult(
        plan=plan,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _validate_idx_file(idx_path: Path, errors: list[str]) -> None:
    if not idx_path.exists() or not idx_path.is_file():
        errors.append(f"IDX file does not exist: {idx_path}")


def _validate_non_negative(name: str, value: int, errors: list[str]) -> None:
    if value < 0:
        errors.append(f"{name} must be non-negative.")
