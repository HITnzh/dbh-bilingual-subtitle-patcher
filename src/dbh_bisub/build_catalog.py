from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import load_catalog, merge_catalogs, save_catalog
from .discovery import CatalogDiscoveryReport, discover_catalogs
from .quality import (
    DEFAULT_MAX_LINE_CHARS,
    DEFAULT_MAX_LINES,
    DEFAULT_MAX_TOTAL_CHARS,
    inspect_catalog_quality,
)
from .terminology import apply_terminology_to_catalog, load_terminology


@dataclass(frozen=True)
class BuildCatalogResult:
    output: str
    english: str | None
    chinese: str | None
    merge_report: str | None
    lint_report: str | None
    discovery: dict[str, Any] | None
    merge: dict[str, Any] | None
    lint: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        lint_ok = self.lint is None or bool(self.lint.get("ok"))
        merge_ok = self.merge is None or bool(self.merge.get("ok"))
        return not self.errors and lint_ok and merge_ok

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def build_bilingual_catalog(
    *,
    output: Path | str,
    fileparser_output: Path | str | None = None,
    english: Path | str | None = None,
    chinese: Path | str | None = None,
    terms: Path | str | None = None,
    merge_report: Path | str | None = None,
    lint_report: Path | str | None = None,
    max_lines: int = DEFAULT_MAX_LINES,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> BuildCatalogResult:
    output_path = Path(output)
    merge_report_path = Path(merge_report) if merge_report else None
    lint_report_path = Path(lint_report) if lint_report else None
    errors: list[str] = []
    warnings: list[str] = []

    base_dir = Path(fileparser_output) if fileparser_output else None
    discovery_report: CatalogDiscoveryReport | None = None
    if english is None or chinese is None:
        if base_dir is None:
            errors.append("Pass --english and --chinese, or pass --fileparser-output for auto-discovery.")
        else:
            discovery_report = discover_catalogs(base_dir)
            warnings.extend(discovery_report.warnings)
            errors.extend(discovery_report.errors)
            if english is None and discovery_report.recommended_english:
                english = discovery_report.recommended_english
            if chinese is None and discovery_report.recommended_chinese:
                chinese = discovery_report.recommended_chinese
            if english is None:
                errors.append("No English catalog was selected.")
            if chinese is None:
                errors.append("No Chinese catalog was selected.")

    english_path = _resolve_catalog_path(english, base_dir) if english is not None else None
    chinese_path = _resolve_catalog_path(chinese, base_dir) if chinese is not None else None
    if errors:
        return BuildCatalogResult(
            output=str(output_path),
            english=str(english_path) if english_path else None,
            chinese=str(chinese_path) if chinese_path else None,
            merge_report=str(merge_report_path) if merge_report_path else None,
            lint_report=str(lint_report_path) if lint_report_path else None,
            discovery=discovery_report.to_dict() if discovery_report else None,
            merge=None,
            lint=None,
            errors=errors,
            warnings=warnings,
        )

    assert english_path is not None
    assert chinese_path is not None
    english_catalog = load_catalog(english_path)
    chinese_catalog = load_catalog(chinese_path)
    terminology_report = None

    if terms:
        rules = load_terminology(terms)
        chinese_catalog, terminology_report = apply_terminology_to_catalog(chinese_catalog, rules)

    merge_result = merge_catalogs(english_catalog, chinese_catalog)
    save_catalog(output_path, merge_result.catalog)
    merge_data = merge_result.report.to_dict()
    if terminology_report:
        merge_data["terminology"] = terminology_report.to_dict()
    if merge_report_path:
        _write_json(merge_report_path, merge_data)

    lint_result = inspect_catalog_quality(
        merge_result.catalog,
        max_lines=max_lines,
        max_line_chars=max_line_chars,
        max_total_chars=max_total_chars,
    )
    lint_data = lint_result.to_dict()
    if lint_report_path:
        _write_json(lint_report_path, lint_data)

    return BuildCatalogResult(
        output=str(output_path),
        english=str(english_path),
        chinese=str(chinese_path),
        merge_report=str(merge_report_path) if merge_report_path else None,
        lint_report=str(lint_report_path) if lint_report_path else None,
        discovery=discovery_report.to_dict() if discovery_report else None,
        merge=merge_data,
        lint=lint_data,
        errors=errors,
        warnings=warnings,
    )


def _resolve_catalog_path(path: Path | str | None, base_dir: Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    if candidate.is_absolute() or candidate.exists() or base_dir is None:
        return candidate
    base_candidate = base_dir / candidate
    if base_candidate.exists():
        return base_candidate
    return candidate


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
