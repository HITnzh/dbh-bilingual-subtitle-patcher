from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import load_catalog
from .discovery import discover_catalogs
from .prepare import BILINGUAL_CATALOG_JSON, CATALOG_DIR, EXTRACTED_DIR, GENERATED_DIR, REPORTS_DIR


@dataclass(frozen=True)
class ValidationCheck:
    id: str
    status: str
    message: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PatchValidationResult:
    ok: bool
    work_dir: str
    discovery: dict[str, Any] | None
    checks: list[ValidationCheck]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "work_dir": self.work_dir,
            "discovery": self.discovery,
            "checks": [check.to_dict() for check in self.checks],
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_patch_workdir(
    work_dir: Path | str,
    *,
    target: Path | str | None = None,
    file_size_table: Path | str | None = None,
    allow_missing_file_size_table: bool = False,
) -> PatchValidationResult:
    root = Path(work_dir)
    checks: list[ValidationCheck] = []
    errors: list[str] = []
    warnings: list[str] = []
    discovery_data: dict[str, Any] | None = None

    if not root.exists() or not root.is_dir():
        _blocked(checks, errors, "work_dir", f"Work directory does not exist: {root}", {"path": str(root)})
        return _result(root, discovery_data, checks, errors, warnings)
    _ok(checks, "work_dir", "Work directory exists.", {"path": str(root)})

    for name in (CATALOG_DIR, EXTRACTED_DIR, GENERATED_DIR, REPORTS_DIR):
        directory = root / name
        if directory.exists() and directory.is_dir():
            _ok(checks, f"{name}_dir", f"{name}/ directory exists.", {"path": str(directory)})
        else:
            _blocked(checks, errors, f"{name}_dir", f"{name}/ directory does not exist: {directory}", {"path": str(directory)})

    catalog_path = root / CATALOG_DIR / BILINGUAL_CATALOG_JSON
    if catalog_path.exists() and catalog_path.is_file():
        try:
            catalog = load_catalog(catalog_path)
            if catalog.count > 0:
                _ok(checks, "bilingual_catalog", "Staged bilingual catalog is readable.", {"path": str(catalog_path), "entries": catalog.count})
            else:
                _warn(checks, warnings, "bilingual_catalog", "Staged bilingual catalog contains no entries.", {"path": str(catalog_path), "entries": 0})
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            _blocked(checks, errors, "bilingual_catalog", f"Staged bilingual catalog is not readable: {exc}", {"path": str(catalog_path)})
    else:
        _blocked(checks, errors, "bilingual_catalog", f"Staged bilingual catalog does not exist: {catalog_path}", {"path": str(catalog_path)})

    extracted_dir = root / EXTRACTED_DIR
    if extracted_dir.exists() and extracted_dir.is_dir():
        discovery = discover_catalogs(extracted_dir)
        discovery_data = discovery.to_dict()
        if discovery.errors:
            for error in discovery.errors:
                _blocked(checks, errors, "catalog_discovery", error, {"path": str(extracted_dir)})
        else:
            _ok(
                checks,
                "catalog_discovery",
                "Extracted JSON catalogs were scanned.",
                {"files": len(discovery.files), "chinese_candidates": discovery.chinese_candidates},
            )
        _validate_target(root, target, discovery.chinese_candidates, checks, errors)
    else:
        _blocked(checks, errors, "catalog_discovery", f"Cannot scan missing extracted directory: {extracted_dir}", {"path": str(extracted_dir)})

    _validate_file_size_table(root, file_size_table, allow_missing_file_size_table, checks, errors, warnings)

    return _result(root, discovery_data, checks, errors, warnings)


def save_patch_validation_result(path: Path | str, result: PatchValidationResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_target(
    root: Path,
    target: Path | str | None,
    chinese_candidates: list[str],
    checks: list[ValidationCheck],
    errors: list[str],
) -> None:
    if target is not None:
        target_path = _resolve_extracted_path(root, target)
        if not target_path.exists() or not target_path.is_file():
            _blocked(checks, errors, "target_catalog", f"Target catalog does not exist: {target_path}", {"path": str(target_path)})
            return
        try:
            catalog = load_catalog(target_path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            _blocked(checks, errors, "target_catalog", f"Target catalog is not readable: {exc}", {"path": str(target_path)})
            return
        _ok(checks, "target_catalog", "Explicit target catalog is readable.", {"path": str(target_path), "entries": catalog.count})
        return

    if len(chinese_candidates) == 1:
        _ok(checks, "target_catalog", "Single Chinese target catalog was found.", {"target": chinese_candidates[0]})
        return
    if not chinese_candidates:
        _blocked(checks, errors, "target_catalog", "No Chinese target catalog was found in extracted/.", {"candidates": []})
        return
    _blocked(
        checks,
        errors,
        "target_catalog",
        "Multiple Chinese target catalogs were found; pass --target explicitly.",
        {"candidates": chinese_candidates},
    )


def _validate_file_size_table(
    root: Path,
    file_size_table: Path | str | None,
    allow_missing: bool,
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
) -> None:
    if file_size_table is not None:
        table = _resolve_path(root, file_size_table)
        if table.exists() and table.is_file():
            _ok(checks, "file_size_table", "Explicit FileSizeTable exists.", {"path": str(table)})
        else:
            _blocked(checks, errors, "file_size_table", f"FileSizeTable does not exist: {table}", {"path": str(table)})
        return

    tables = _discover_file_size_tables(root)
    if len(tables) == 1:
        _ok(checks, "file_size_table", "Single FileSizeTable was found.", {"path": str(tables[0])})
        return
    if not tables:
        message = "No FileSizeTable was found; repack planning will be unavailable."
        if allow_missing:
            _warn(checks, warnings, "file_size_table", message, {})
        else:
            _blocked(checks, errors, "file_size_table", message, {})
        return
    _blocked(
        checks,
        errors,
        "file_size_table",
        "Multiple FileSizeTable files were found; pass --file-size-table explicitly.",
        {"candidates": [str(path) for path in tables]},
    )


def _discover_file_size_tables(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.name.lower().endswith(".filesizetable")),
        key=lambda path: str(path).lower(),
    )


def _resolve_extracted_path(root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    rooted = root / candidate
    if rooted.exists():
        return rooted
    return root / EXTRACTED_DIR / candidate


def _resolve_path(root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return root / candidate


def _ok(checks: list[ValidationCheck], check_id: str, message: str, details: dict[str, Any]) -> None:
    checks.append(ValidationCheck(check_id, "ok", message, details))


def _warn(
    checks: list[ValidationCheck],
    warnings: list[str],
    check_id: str,
    message: str,
    details: dict[str, Any],
) -> None:
    warnings.append(message)
    checks.append(ValidationCheck(check_id, "warning", message, details))


def _blocked(
    checks: list[ValidationCheck],
    errors: list[str],
    check_id: str,
    message: str,
    details: dict[str, Any],
) -> None:
    errors.append(message)
    checks.append(ValidationCheck(check_id, "blocked", message, details))


def _result(
    work_dir: Path,
    discovery: dict[str, Any] | None,
    checks: list[ValidationCheck],
    errors: list[str],
    warnings: list[str],
) -> PatchValidationResult:
    return PatchValidationResult(
        ok=not errors,
        work_dir=str(work_dir),
        discovery=discovery,
        checks=checks,
        errors=errors,
        warnings=warnings,
    )
