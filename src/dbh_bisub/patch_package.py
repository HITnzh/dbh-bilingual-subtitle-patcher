from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .constants import INDEX_FILE
from .idx_archive import default_idx_file, plan_idx_repack
from .prepare import GENERATED_DIR, REPORTS_DIR

PACKAGE_DIR = "package"
PACKAGE_MANIFEST_JSON = "package-manifest.json"


@dataclass(frozen=True)
class PackageFile:
    relative_path: str
    source: str
    packaged: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchPackageResult:
    ok: bool
    work_dir: str
    generated_dir: str
    package_dir: str
    manifest_path: str | None
    files: list[PackageFile]
    idx_file: str | None
    file_size_table: str | None
    repack_plan: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "work_dir": self.work_dir,
            "generated_dir": self.generated_dir,
            "package_dir": self.package_dir,
            "manifest_path": self.manifest_path,
            "files": [file.to_dict() for file in self.files],
            "idx_file": self.idx_file,
            "file_size_table": self.file_size_table,
            "repack_plan": self.repack_plan,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def package_patch_workdir(
    work_dir: Path | str,
    *,
    package_dir: Path | str | None = None,
    manifest: Path | str | None = None,
    game_dir: Path | str | None = None,
    idx_file: Path | str | None = None,
    file_size_table: Path | str | None = None,
    idx_detroit: Path | str | None = None,
) -> PatchPackageResult:
    root = Path(work_dir)
    generated_dir = root / GENERATED_DIR
    target_dir = _resolve_package_dir(root, package_dir)
    manifest_path = _resolve_manifest(root, manifest)
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Work directory does not exist: {root}")
        return _result(root, generated_dir, target_dir, manifest_path, [], None, None, None, errors, warnings)

    if not generated_dir.exists() or not generated_dir.is_dir():
        errors.append(f"Generated directory does not exist: {generated_dir}")
        return _result(root, generated_dir, target_dir, manifest_path, [], None, None, None, errors, warnings)

    generated_files = _generated_files(generated_dir)
    if not generated_files:
        errors.append(f"Generated directory contains no files: {generated_dir}")
        return _result(root, generated_dir, target_dir, manifest_path, [], None, None, None, errors, warnings)

    packaged_files: list[PackageFile] = []
    for source in generated_files:
        relative = source.relative_to(generated_dir)
        packaged = target_dir / relative
        packaged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, packaged)
        packaged_files.append(_package_file(generated_dir, source, packaged))

    resolved_table, table_warnings = _resolve_file_size_table(root, file_size_table)
    warnings.extend(table_warnings)
    resolved_idx, idx_warnings = _resolve_idx_file(root, game_dir=game_dir, idx_file=idx_file)
    warnings.extend(idx_warnings)

    repack_plan: dict[str, Any] | None = None
    if resolved_idx is not None and resolved_table is not None:
        plan = plan_idx_repack(resolved_idx, resolved_table, idx_detroit=idx_detroit, dry_run=True)
        repack_plan = plan.to_dict()
        if not plan.ok:
            warnings.extend(f"Repack plan blocked: {message}" for message in plan.errors)

    result = _result(
        root,
        generated_dir,
        target_dir,
        manifest_path,
        packaged_files,
        resolved_idx,
        resolved_table,
        repack_plan,
        errors,
        warnings,
    )
    _write_json(manifest_path, result.to_dict())
    return result


def save_patch_package_result(path: Path | str, result: PatchPackageResult) -> None:
    _write_json(Path(path), result.to_dict())


def _result(
    root: Path,
    generated_dir: Path,
    package_dir: Path,
    manifest_path: Path | None,
    files: list[PackageFile],
    idx_file: Path | None,
    file_size_table: Path | None,
    repack_plan: dict[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> PatchPackageResult:
    return PatchPackageResult(
        ok=not errors,
        work_dir=str(root),
        generated_dir=str(generated_dir),
        package_dir=str(package_dir),
        manifest_path=str(manifest_path) if manifest_path is not None else None,
        files=files,
        idx_file=str(idx_file) if idx_file is not None else None,
        file_size_table=str(file_size_table) if file_size_table is not None else None,
        repack_plan=repack_plan,
        errors=errors,
        warnings=warnings,
    )


def _resolve_package_dir(root: Path, package_dir: Path | str | None) -> Path:
    if package_dir is None:
        return root / PACKAGE_DIR
    return _resolve_path(root, package_dir)


def _resolve_manifest(root: Path, manifest: Path | str | None) -> Path:
    if manifest is None:
        return root / REPORTS_DIR / PACKAGE_MANIFEST_JSON
    return _resolve_path(root, manifest)


def _resolve_file_size_table(root: Path, file_size_table: Path | str | None) -> tuple[Path | None, list[str]]:
    if file_size_table is not None:
        candidate = _resolve_path(root, file_size_table)
        if not candidate.exists() or not candidate.is_file():
            return None, [f"FileSizeTable does not exist: {candidate}"]
        return candidate, []

    candidates = _discover_file_size_tables(root)
    if len(candidates) == 1:
        return candidates[0], []
    if not candidates:
        return None, ["No FileSizeTable was found; repack plan is omitted."]
    return None, ["Multiple FileSizeTable files were found; pass --file-size-table explicitly."]


def _resolve_idx_file(
    root: Path,
    *,
    game_dir: Path | str | None,
    idx_file: Path | str | None,
) -> tuple[Path | None, list[str]]:
    if idx_file is not None:
        candidate = _resolve_path(root, idx_file)
        if not candidate.exists() or not candidate.is_file():
            return None, [f"IDX file does not exist: {candidate}"]
        return candidate, []

    resolved_game_dir = Path(game_dir) if game_dir is not None else _game_dir_from_prepare_report(root)
    if resolved_game_dir is not None:
        candidate = default_idx_file(resolved_game_dir)
        if candidate.exists() and candidate.is_file():
            return candidate, []
        return None, [f"IDX file does not exist: {candidate}"]

    return None, [f"No game directory or {INDEX_FILE} was provided; repack plan is omitted."]


def _game_dir_from_prepare_report(root: Path) -> Path | None:
    report = root / REPORTS_DIR / "patch-plan.json"
    if not report.exists() or not report.is_file():
        return None
    try:
        data = json.loads(report.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    game_dir = data.get("game_dir")
    return Path(game_dir) if isinstance(game_dir, str) and game_dir else None


def _discover_file_size_tables(root: Path) -> list[Path]:
    candidates = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.name.lower().endswith(".filesizetable")
    ]
    return sorted(candidates, key=lambda path: str(path).lower())


def _generated_files(generated_dir: Path) -> list[Path]:
    return sorted((path for path in generated_dir.rglob("*") if path.is_file()), key=lambda path: str(path).lower())


def _package_file(generated_dir: Path, source: Path, packaged: Path) -> PackageFile:
    return PackageFile(
        relative_path=str(source.relative_to(generated_dir)),
        source=str(source),
        packaged=str(packaged),
        size=packaged.stat().st_size,
        sha256=_sha256(packaged),
    )


def _resolve_path(root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return root / candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
