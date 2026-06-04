from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .prepare import EXTRACTED_DIR, REPORTS_DIR

PACKAGE_MANIFEST_JSON = "package-manifest.json"
MATERIALIZE_MANIFEST_JSON = "materialize-manifest.json"


@dataclass(frozen=True)
class MaterializedFile:
    relative_path: str
    packaged: str
    target: str
    original_size: int
    original_sha256: str
    patched_size: int
    patched_sha256: str
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchMaterializeResult:
    ok: bool
    work_dir: str
    package_manifest: str
    target_dir: str
    manifest_path: str | None
    files: list[MaterializedFile]
    suppressed_files: list[str]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "work_dir": self.work_dir,
            "package_manifest": self.package_manifest,
            "target_dir": self.target_dir,
            "manifest_path": self.manifest_path,
            "files": [file.to_dict() for file in self.files],
            "suppressed_files": self.suppressed_files,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def materialize_patch_package(
    work_dir: Path | str,
    *,
    package_manifest: Path | str | None = None,
    target_dir: Path | str | None = None,
    manifest: Path | str | None = None,
) -> PatchMaterializeResult:
    root = Path(work_dir)
    package_manifest_path = _resolve_package_manifest(root, package_manifest)
    target_root = _resolve_target_dir(root, target_dir)
    manifest_path = _resolve_manifest(root, manifest)
    errors: list[str] = []
    warnings: list[str] = []
    files: list[MaterializedFile] = []
    suppressed_files: list[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Work directory does not exist: {root}")
        return _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)

    if not package_manifest_path.exists() or not package_manifest_path.is_file():
        errors.append(f"Package manifest does not exist: {package_manifest_path}")
        return _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)

    if not target_root.exists() or not target_root.is_dir():
        errors.append(f"Target extracted directory does not exist: {target_root}")
        return _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)

    data = json.loads(package_manifest_path.read_text(encoding="utf-8-sig"))
    package_files = data.get("files")
    if not isinstance(package_files, list) or not package_files:
        errors.append(f"Package manifest contains no files: {package_manifest_path}")
        return _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)

    planned: list[tuple[str, Path, Path, str]] = []
    for item in package_files:
        if not isinstance(item, dict):
            errors.append("Package manifest contains a non-object file entry.")
            continue
        relative_path = item.get("relative_path")
        expected_sha = item.get("sha256")
        packaged_path = item.get("packaged")
        if not isinstance(relative_path, str) or not relative_path:
            errors.append("Package manifest file entry is missing relative_path.")
            continue
        if not isinstance(expected_sha, str) or not expected_sha:
            errors.append(f"Package manifest file entry is missing sha256: {relative_path}")
            continue

        packaged = _resolve_packaged_path(root, packaged_path, relative_path)
        target = _safe_target(target_root, relative_path, errors)
        if target is None:
            continue
        if not packaged.exists() or not packaged.is_file():
            errors.append(f"Packaged file does not exist: {packaged}")
            continue
        actual_sha = _sha256(packaged)
        if actual_sha != expected_sha:
            errors.append(f"Packaged file hash mismatch: {packaged}")
            continue
        if not target.exists() or not target.is_file():
            errors.append(f"Extracted target file does not exist: {target}")
            continue
        planned.append((relative_path, packaged, target, actual_sha))

    if errors:
        return _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)

    planned_relatives = {relative_path.replace("\\", "/").lower() for relative_path, _, _, _ in planned}
    for relative_path, packaged, target, patched_sha in planned:
        original_sha = _sha256(target)
        original_size = target.stat().st_size
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packaged, target)
        files.append(
            MaterializedFile(
                relative_path=relative_path,
                packaged=str(packaged),
                target=str(target),
                original_size=original_size,
                original_sha256=original_sha,
                patched_size=target.stat().st_size,
                patched_sha256=patched_sha,
                changed=original_sha != patched_sha,
            )
        )
        suppressed_files.extend(_suppress_target_text_sibling(relative_path, target, planned_relatives))

    result = _result(root, package_manifest_path, target_root, manifest_path, files, suppressed_files, errors, warnings)
    _write_json(manifest_path, result.to_dict())
    return result


def save_patch_materialize_result(path: Path | str, result: PatchMaterializeResult) -> None:
    _write_json(Path(path), result.to_dict())


def _result(
    root: Path,
    package_manifest: Path,
    target_dir: Path,
    manifest_path: Path | None,
    files: list[MaterializedFile],
    suppressed_files: list[str],
    errors: list[str],
    warnings: list[str],
) -> PatchMaterializeResult:
    return PatchMaterializeResult(
        ok=not errors,
        work_dir=str(root),
        package_manifest=str(package_manifest),
        target_dir=str(target_dir),
        manifest_path=str(manifest_path) if manifest_path is not None else None,
        files=files,
        suppressed_files=suppressed_files,
        errors=errors,
        warnings=warnings,
    )


def _resolve_package_manifest(root: Path, package_manifest: Path | str | None) -> Path:
    if package_manifest is None:
        return root / REPORTS_DIR / PACKAGE_MANIFEST_JSON
    return _resolve_path(root, package_manifest)


def _resolve_target_dir(root: Path, target_dir: Path | str | None) -> Path:
    if target_dir is None:
        return root / EXTRACTED_DIR
    return _resolve_path(root, target_dir)


def _resolve_manifest(root: Path, manifest: Path | str | None) -> Path:
    if manifest is None:
        return root / REPORTS_DIR / MATERIALIZE_MANIFEST_JSON
    return _resolve_path(root, manifest)


def _resolve_packaged_path(root: Path, packaged_path: Any, relative_path: str) -> Path:
    if isinstance(packaged_path, str) and packaged_path:
        candidate = Path(packaged_path)
        if candidate.is_absolute():
            return candidate
        if candidate.exists():
            return candidate
        return root / candidate
    return root / "package" / relative_path


def _safe_target(root: Path, relative_path: str, errors: list[str]) -> Path | None:
    candidate = root / relative_path
    try:
        resolved_root = root.resolve()
        resolved_candidate = candidate.resolve()
    except OSError as exc:
        errors.append(f"Could not resolve materialize target: {candidate}: {exc}")
        return None
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        errors.append(f"Refusing to materialize outside extracted directory: {relative_path}")
        return None
    return candidate


def _suppress_target_text_sibling(relative_path: str, target: Path, planned_relatives: set[str]) -> list[str]:
    normalized = relative_path.replace("\\", "/").lower()
    if not normalized.endswith(".dat"):
        return []

    sibling_relative = normalized[:-4] + ".txt"
    if sibling_relative in planned_relatives:
        return []

    sibling = target.with_suffix(".txt")
    if not sibling.is_file():
        return []

    sibling.unlink()
    return [str(sibling)]


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
