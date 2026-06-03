from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    id: str
    display_name: str
    purpose: str
    default_names: tuple[str, ...]
    docs_url: str
    help_args: tuple[str, ...] = ("-h",)


FILE_PARSER = ToolSpec(
    id="file_parser",
    display_name="DBH FileParser",
    purpose="Extract DBH translation keys and language JSON files from BigFile_PC.d* archives.",
    default_names=("FileParser.exe", "FileParser"),
    docs_url="https://github.com/detroitbecometext/dbh-file-parser",
)

IDX_DETROIT = ToolSpec(
    id="idx_detroit",
    display_name="IDX-Detroit",
    purpose="Extract and repack raw Detroit: Become Human BigFile_PC.idx archive data.",
    default_names=("IDX_Detroit.exe", "IDX_Detroit", "IDX Detroit.exe"),
    docs_url="https://github.com/systemsiteseason/IDX-Detroit",
)

TOOL_SPECS = {
    FILE_PARSER.id: FILE_PARSER,
    IDX_DETROIT.id: IDX_DETROIT,
}


@dataclass(frozen=True)
class ToolProbe:
    id: str
    display_name: str
    purpose: str
    configured_path: str | None
    resolved_path: str | None
    available: bool
    source: str
    default_names: list[str]
    docs_url: str
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolchainReport:
    tools: list[ToolProbe]

    @property
    def ok(self) -> bool:
        return all(tool.available for tool in self.tools)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tools": [tool.to_dict() for tool in self.tools],
        }


def _normalize_explicit_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def probe_tool(spec: ToolSpec, explicit_path: str | Path | None = None) -> ToolProbe:
    errors: list[str] = []
    warnings: list[str] = []
    configured_path = str(explicit_path) if explicit_path is not None else None

    if explicit_path is not None:
        candidate = _normalize_explicit_path(explicit_path)
        if not candidate.exists():
            errors.append(f"Configured path does not exist: {candidate}")
            return _probe_result(spec, configured_path, None, "explicit", errors, warnings)
        if not candidate.is_file():
            errors.append(f"Configured path is not a file: {candidate}")
            return _probe_result(spec, configured_path, None, "explicit", errors, warnings)
        return _probe_result(spec, configured_path, str(candidate), "explicit", errors, warnings)

    for executable_name in spec.default_names:
        resolved = shutil.which(executable_name)
        if resolved:
            return _probe_result(spec, None, resolved, "path", errors, warnings)

    names = ", ".join(spec.default_names)
    warnings.append(f"Not found on PATH. Tried: {names}")
    return _probe_result(spec, None, None, "missing", errors, warnings)


def _probe_result(
    spec: ToolSpec,
    configured_path: str | None,
    resolved_path: str | None,
    source: str,
    errors: list[str],
    warnings: list[str],
) -> ToolProbe:
    return ToolProbe(
        id=spec.id,
        display_name=spec.display_name,
        purpose=spec.purpose,
        configured_path=configured_path,
        resolved_path=resolved_path,
        available=resolved_path is not None and not errors,
        source=source,
        default_names=list(spec.default_names),
        docs_url=spec.docs_url,
        errors=errors,
        warnings=warnings,
    )


def inspect_toolchain(
    *,
    file_parser: str | Path | None = None,
    idx_detroit: str | Path | None = None,
) -> ToolchainReport:
    return ToolchainReport(
        tools=[
            probe_tool(FILE_PARSER, file_parser),
            probe_tool(IDX_DETROIT, idx_detroit),
        ]
    )


def build_file_parser_extract_command(
    executable: str | Path,
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    verbose: bool = False,
) -> list[str]:
    command = [str(executable)]
    if verbose:
        command.append("-v")
    command.extend(["-i", str(input_dir), "-o", str(output_dir)])
    return command


def build_idx_extract_command(
    executable: str | Path,
    idx_file: str | Path,
    *,
    archive_id: int = 1,
    object_count: int = 0,
) -> list[str]:
    return [str(executable), "-e", str(idx_file), str(archive_id), str(object_count)]


def build_idx_repack_command(
    executable: str | Path,
    idx_file: str | Path,
    file_size_table: str | Path,
) -> list[str]:
    return [str(executable), "-p", str(idx_file), str(file_size_table)]


def format_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)
