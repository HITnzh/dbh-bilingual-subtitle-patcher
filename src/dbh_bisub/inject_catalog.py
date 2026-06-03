from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import KEY_FIELDS, TEXT_FIELDS, TextCatalog, load_catalog


@dataclass(frozen=True)
class InjectionIssue:
    key: str
    level: str
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogInjectionReport:
    source_entries: int
    target_entries: int
    updated: int
    unchanged: int
    skipped: int
    missing_in_target: list[str]
    missing_in_source: list[str]
    issues: list[InjectionIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source_entries": self.source_entries,
            "target_entries": self.target_entries,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "missing_in_target": self.missing_in_target,
            "missing_in_source": self.missing_in_source,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class CatalogInjectionResult:
    output: str
    report: CatalogInjectionReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.report.ok,
            "output": self.output,
            "report": self.report.to_dict(),
        }


@dataclass
class _Stats:
    target_entries: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    target_keys: set[str] | None = None
    missing_in_source: set[str] | None = None
    issues: list[InjectionIssue] | None = None

    def __post_init__(self) -> None:
        self.target_keys = set()
        self.missing_in_source = set()
        self.issues = []


def inject_catalog_file(
    *,
    source: Path | str,
    target: Path | str,
    output: Path | str,
    report: Path | str | None = None,
    text_field: str | None = None,
) -> CatalogInjectionResult:
    source_catalog = load_catalog(source)
    target_path = Path(target)
    target_data = json.loads(target_path.read_text(encoding="utf-8-sig"))

    patched_data, injection_report = inject_catalog_data(source_catalog, target_data, text_field=text_field)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(patched_data, ensure_ascii=False, indent=2), encoding="utf-8")

    if report:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(injection_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return CatalogInjectionResult(output=str(output_path), report=injection_report)


def inject_catalog_data(
    source_catalog: TextCatalog,
    target_data: Any,
    *,
    text_field: str | None = None,
) -> tuple[Any, CatalogInjectionReport]:
    stats = _Stats()
    patched_data = _patch_node(target_data, source_catalog, stats, text_field=text_field)
    assert stats.target_keys is not None
    assert stats.missing_in_source is not None
    assert stats.issues is not None
    missing_in_target = [key for key in source_catalog.keys() if key not in stats.target_keys]
    issues = list(stats.issues)
    for key in missing_in_target:
        issues.append(InjectionIssue(key, "warning", "missing_in_target", "Source key was not found in target catalog."))

    report = CatalogInjectionReport(
        source_entries=source_catalog.count,
        target_entries=stats.target_entries,
        updated=stats.updated,
        unchanged=stats.unchanged,
        skipped=stats.skipped,
        missing_in_target=missing_in_target,
        missing_in_source=sorted(stats.missing_in_source),
        issues=issues,
    )
    return patched_data, report


def _patch_node(data: Any, source_catalog: TextCatalog, stats: _Stats, *, text_field: str | None) -> Any:
    if isinstance(data, dict):
        if "entries" in data and isinstance(data["entries"], list):
            patched = dict(data)
            patched["entries"] = _patch_sequence(data["entries"], source_catalog, stats, text_field=text_field)
            return patched
        if "items" in data and isinstance(data["items"], list):
            patched = dict(data)
            patched["items"] = _patch_sequence(data["items"], source_catalog, stats, text_field=text_field)
            return patched
        if "strings" in data and isinstance(data["strings"], (dict, list)):
            patched = dict(data)
            patched["strings"] = _patch_node(data["strings"], source_catalog, stats, text_field=text_field)
            return patched
        return _patch_mapping(data, source_catalog, stats, text_field=text_field)
    if isinstance(data, list):
        return _patch_sequence(data, source_catalog, stats, text_field=text_field)
    raise ValueError("Unsupported target JSON shape; expected object or list.")


def _patch_mapping(
    data: dict[str, Any],
    source_catalog: TextCatalog,
    stats: _Stats,
    *,
    text_field: str | None,
) -> dict[str, Any]:
    patched: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str):
            patched[key] = _replacement_for_key(key, value, source_catalog, stats)
            continue
        if isinstance(value, dict):
            patched[key] = _patch_object_entry(str(key), value, source_catalog, stats, text_field=text_field)
            continue
        patched[key] = value
        stats.skipped += 1
    return patched


def _patch_sequence(items: list[Any], source_catalog: TextCatalog, stats: _Stats, *, text_field: str | None) -> list[Any]:
    patched: list[Any] = []
    for index, item in enumerate(items):
        if isinstance(item, str):
            patched.append(_replacement_for_key(str(index), item, source_catalog, stats))
            continue
        if isinstance(item, dict):
            key = _entry_key(item)
            if key is None:
                patched.append(item)
                stats.skipped += 1
                assert stats.issues is not None
                stats.issues.append(InjectionIssue(str(index), "warning", "missing_key", "Target entry has no key field."))
                continue
            patched.append(_patch_object_entry(key, item, source_catalog, stats, text_field=text_field))
            continue
        patched.append(item)
        stats.skipped += 1
    return patched


def _patch_object_entry(
    key: str,
    item: dict[str, Any],
    source_catalog: TextCatalog,
    stats: _Stats,
    *,
    text_field: str | None,
) -> dict[str, Any]:
    field = _entry_text_field(item, explicit_field=text_field)
    if field is None:
        stats.skipped += 1
        assert stats.issues is not None
        stats.issues.append(InjectionIssue(key, "warning", "missing_text", "Target entry has no text field."))
        return dict(item)

    current = item.get(field)
    if not isinstance(current, str):
        stats.skipped += 1
        assert stats.issues is not None
        stats.issues.append(InjectionIssue(key, "warning", "non_string_text", "Target text field is not a string."))
        return dict(item)

    patched = dict(item)
    patched[field] = _replacement_for_key(key, current, source_catalog, stats)
    return patched


def _replacement_for_key(key: str, current: str, source_catalog: TextCatalog, stats: _Stats) -> str:
    assert stats.target_keys is not None
    assert stats.missing_in_source is not None
    stats.target_entries += 1
    stats.target_keys.add(key)

    replacement = source_catalog.get_text(key)
    if replacement == "":
        stats.missing_in_source.add(key)
        return current
    if replacement == current:
        stats.unchanged += 1
        return current
    stats.updated += 1
    return replacement


def _entry_key(item: dict[str, Any]) -> str | None:
    for field in KEY_FIELDS:
        value = item.get(field)
        if value is not None:
            return str(value)
    return None


def _entry_text_field(item: dict[str, Any], *, explicit_field: str | None) -> str | None:
    if explicit_field:
        return explicit_field if explicit_field in item else None
    for field in TEXT_FIELDS:
        if field in item:
            return field
    return None
