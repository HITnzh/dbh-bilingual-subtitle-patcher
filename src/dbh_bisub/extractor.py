from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import subprocess
from typing import Any

from .game_files import inspect_game_dir
from .toolchain import FILE_PARSER, build_file_parser_extract_command, format_command, probe_tool


@dataclass(frozen=True)
class ExtractionPlan:
    game_dir: str
    output_dir: str
    file_parser: str | None
    dry_run: bool
    force: bool
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
class ExtractionResult:
    plan: ExtractionPlan
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


def plan_extraction(
    game_dir: Path | str,
    output_dir: Path | str,
    *,
    file_parser: Path | str | None = None,
    dry_run: bool = True,
    force: bool = False,
    verbose: bool = False,
) -> ExtractionPlan:
    game_root = Path(game_dir)
    output_root = Path(output_dir)
    errors: list[str] = []
    warnings: list[str] = []

    game_report = inspect_game_dir(game_root)
    errors.extend(game_report.errors)
    warnings.extend(game_report.warnings)

    tool = probe_tool(FILE_PARSER, file_parser)
    errors.extend(tool.errors)
    warnings.extend(tool.warnings)
    if not tool.available:
        errors.append("FileParser is not available. Pass --file-parser or add it to PATH.")

    if output_root.exists() and output_root.is_file():
        errors.append(f"Output path is a file, not a directory: {output_root}")
    elif output_root.exists() and any(output_root.iterdir()) and not force:
        errors.append(f"Output directory is not empty: {output_root}. Use --force to allow reuse.")

    executable = tool.resolved_path or str(file_parser or "FileParser")
    command = build_file_parser_extract_command(executable, game_root, output_root, verbose=verbose)
    return ExtractionPlan(
        game_dir=str(game_root),
        output_dir=str(output_root),
        file_parser=tool.resolved_path,
        dry_run=dry_run,
        force=force,
        command=command,
        command_text=format_command(command),
        errors=errors,
        warnings=warnings,
    )


def run_extraction(plan: ExtractionPlan) -> ExtractionResult:
    if not plan.ok or plan.dry_run:
        return ExtractionResult(plan=plan, returncode=None, stdout="", stderr="")

    Path(plan.output_dir).mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            plan.command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return ExtractionResult(plan=plan, returncode=-1, stdout="", stderr=str(exc))
    return ExtractionResult(
        plan=plan,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
