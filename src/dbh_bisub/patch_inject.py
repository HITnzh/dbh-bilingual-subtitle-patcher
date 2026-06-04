from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .discovery import discover_catalogs
from .idx_text_inject import has_idx_text_files, inject_idx_text_tree
from .inject_catalog import CatalogInjectionResult, inject_catalog_file
from .prepare import BILINGUAL_CATALOG_JSON, CATALOG_DIR, EXTRACTED_DIR, GENERATED_DIR, REPORTS_DIR

INJECT_REPORT_JSON = "inject-report.json"


@dataclass(frozen=True)
class PatchInjectResult:
    ok: bool
    work_dir: str
    source: str | None
    target: str | None
    output: str | None
    report_path: str | None
    discovery: dict[str, Any] | None
    injection: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def patch_inject_workdir(
    work_dir: Path | str,
    *,
    source: Path | str | None = None,
    target: Path | str | None = None,
    output: Path | str | None = None,
    report: Path | str | None = None,
    text_field: str | None = None,
    idx_dat_language: str | None = None,
) -> PatchInjectResult:
    root = Path(work_dir)
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Work directory does not exist: {root}")
        return _blocked(root, source, target, output, report, None, errors, warnings)

    source_path = _resolve_source(root, source)
    if not source_path.exists() or not source_path.is_file():
        errors.append(f"Bilingual catalog does not exist: {source_path}")

    target_path: Path | None
    discovery_data: dict[str, Any] | None = None
    if target is None:
        discovery = discover_catalogs(root / EXTRACTED_DIR)
        discovery_data = discovery.to_dict()
        discovery_data["warnings"] = _target_discovery_warnings(discovery.warnings)
        warnings.extend(discovery_data["warnings"])
        errors.extend(discovery.errors)
        candidates = discovery.chinese_candidates
        if len(candidates) == 1:
            target_path = root / EXTRACTED_DIR / candidates[0]
        elif len(candidates) == 0:
            text_target = root / EXTRACTED_DIR
            if has_idx_text_files(text_target):
                target_path = None
                warnings.append("No JSON target catalog was found; using IDX text files from extracted/.")
                output_dir = _resolve_idx_text_output(root, output)
                report_path = _resolve_report(root, report)
                if errors:
                    return _blocked(root, source_path, text_target, output_dir, report_path, discovery_data, errors, warnings)
                result = inject_idx_text_tree(
                    source=source_path,
                    extracted_dir=text_target,
                    output_dir=output_dir,
                    report=report_path,
                    dat_language=idx_dat_language,
                )
                return PatchInjectResult(
                    ok=result.ok,
                    work_dir=str(root),
                    source=str(source_path),
                    target=str(text_target),
                    output=str(output_dir),
                    report_path=str(report_path),
                    discovery=discovery_data,
                    injection=result.to_dict(),
                    errors=[] if result.ok else ["IDX text injection did not update or match any target entries."],
                    warnings=warnings,
                )
            else:
                target_path = None
                errors.append("No Chinese target catalog was found in the extracted directory.")
        else:
            target_path = None
            errors.append("Multiple Chinese target catalogs were found; pass --target explicitly.")
    else:
        target_path = _resolve_path(root, target, default_subdir="extracted")

    if target_path is not None and (not target_path.exists() or not target_path.is_file()):
        errors.append(f"Target catalog does not exist: {target_path}")

    output_path = _resolve_output(root, output, target_path)
    report_path = _resolve_report(root, report)

    if errors:
        return _blocked(root, source_path, target_path, output_path, report_path, discovery_data, errors, warnings)

    assert target_path is not None
    result: CatalogInjectionResult = inject_catalog_file(
        source=source_path,
        target=target_path,
        output=output_path,
        report=report_path,
        text_field=text_field,
    )
    data = result.to_dict()
    return PatchInjectResult(
        ok=data["ok"],
        work_dir=str(root),
        source=str(source_path),
        target=str(target_path),
        output=str(output_path),
        report_path=str(report_path),
        discovery=discovery_data,
        injection=data,
        errors=[],
        warnings=warnings,
    )


def _blocked(
    root: Path,
    source: Path | str | None,
    target: Path | str | None,
    output: Path | str | None,
    report: Path | str | None,
    discovery: dict[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> PatchInjectResult:
    return PatchInjectResult(
        ok=False,
        work_dir=str(root),
        source=str(source) if source is not None else None,
        target=str(target) if target is not None else None,
        output=str(output) if output is not None else None,
        report_path=str(report) if report is not None else None,
        discovery=discovery,
        injection=None,
        errors=errors,
        warnings=warnings,
    )


def _resolve_source(root: Path, source: Path | str | None) -> Path:
    if source is None:
        return root / CATALOG_DIR / BILINGUAL_CATALOG_JSON
    return _resolve_path(root, source, default_subdir=CATALOG_DIR)


def _resolve_output(root: Path, output: Path | str | None, target: Path | None) -> Path:
    if output is not None:
        return _resolve_path(root, output, default_subdir=GENERATED_DIR)
    if target is None:
        return root / GENERATED_DIR / "patched.json"
    try:
        relative = target.relative_to(root / EXTRACTED_DIR)
    except ValueError:
        relative = Path(target.name)
    return root / GENERATED_DIR / relative


def _resolve_idx_text_output(root: Path, output: Path | str | None) -> Path:
    if output is not None:
        return _resolve_path(root, output, default_subdir=GENERATED_DIR)
    return root / GENERATED_DIR


def _resolve_report(root: Path, report: Path | str | None) -> Path:
    if report is not None:
        return _resolve_path(root, report, default_subdir=REPORTS_DIR)
    return root / REPORTS_DIR / INJECT_REPORT_JSON


def _target_discovery_warnings(warnings: list[str]) -> list[str]:
    return [warning for warning in warnings if warning != "No English catalog candidate was found."]


def _resolve_path(root: Path, path: Path | str, *, default_subdir: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    rooted = root / candidate
    if rooted.exists():
        return rooted
    return root / default_subdir / candidate


def save_patch_inject_result(path: Path | str, result: PatchInjectResult) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
