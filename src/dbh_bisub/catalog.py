from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from .merge_subtitles import merge_bilingual_text

KEY_FIELDS = ("key", "id", "name", "hash")
TEXT_FIELDS = ("text", "value", "content", "translation", "source")


@dataclass(frozen=True)
class TextEntry:
    key: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {"key": self.key, "text": self.text}
        if self.metadata:
            data["metadata"] = self.metadata
        return data


@dataclass(frozen=True)
class TextCatalog:
    entries: OrderedDict[str, TextEntry]

    @classmethod
    def empty(cls) -> TextCatalog:
        return cls(OrderedDict())

    @property
    def count(self) -> int:
        return len(self.entries)

    def keys(self) -> list[str]:
        return list(self.entries.keys())

    def get_text(self, key: str) -> str:
        entry = self.entries.get(key)
        return entry.text if entry else ""

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [entry.to_dict() for entry in self.entries.values()]}


@dataclass(frozen=True)
class MergeIssue:
    key: str
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogMergeReport:
    total_english: int
    total_chinese: int
    merged: int
    missing_english: int
    missing_chinese: int
    token_warnings: int
    issues: list[MergeIssue]

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_english": self.total_english,
            "total_chinese": self.total_chinese,
            "merged": self.merged,
            "missing_english": self.missing_english,
            "missing_chinese": self.missing_chinese,
            "token_warnings": self.token_warnings,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class CatalogMergeResult:
    catalog: TextCatalog
    report: CatalogMergeReport


def load_catalog(path: Path | str) -> TextCatalog:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    return catalog_from_json(data)


def save_catalog(path: Path | str, catalog: TextCatalog) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(catalog.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def save_report(path: Path | str, report: CatalogMergeReport) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def catalog_from_json(data: Any) -> TextCatalog:
    if isinstance(data, dict):
        if "entries" in data:
            return _catalog_from_sequence(data["entries"])
        if "strings" in data:
            return catalog_from_json(data["strings"])
        if "items" in data:
            return _catalog_from_sequence(data["items"])
        return _catalog_from_mapping(data)
    if isinstance(data, list):
        return _catalog_from_sequence(data)
    raise ValueError("Unsupported catalog JSON shape; expected object or list.")


def merge_catalogs(english: TextCatalog, chinese: TextCatalog) -> CatalogMergeResult:
    merged_entries: OrderedDict[str, TextEntry] = OrderedDict()
    issues: list[MergeIssue] = []
    missing_english = 0
    missing_chinese = 0
    token_warnings = 0

    ordered_keys = english.keys() + [key for key in chinese.keys() if key not in english.entries]
    for key in ordered_keys:
        english_text = english.get_text(key)
        chinese_text = chinese.get_text(key)
        merge_result = merge_bilingual_text(english_text, chinese_text)
        merged_entries[key] = TextEntry(key=key, text=merge_result.text)

        if not english_text:
            missing_english += 1
            issues.append(MergeIssue(key, "warning", "Missing English text; used Chinese only."))
        if not chinese_text:
            missing_chinese += 1
            issues.append(MergeIssue(key, "warning", "Missing Chinese text; used English only."))
        for warning in merge_result.warnings:
            if warning.startswith("Missing English text") or warning.startswith("Missing Chinese text"):
                continue
            if "Control tokens differ" in warning:
                token_warnings += 1
            issues.append(MergeIssue(key, "warning", warning))

    report = CatalogMergeReport(
        total_english=english.count,
        total_chinese=chinese.count,
        merged=len(merged_entries),
        missing_english=missing_english,
        missing_chinese=missing_chinese,
        token_warnings=token_warnings,
        issues=issues,
    )
    return CatalogMergeResult(TextCatalog(merged_entries), report)


def _catalog_from_mapping(data: dict[str, Any]) -> TextCatalog:
    entries: OrderedDict[str, TextEntry] = OrderedDict()
    for key, value in data.items():
        if isinstance(value, str):
            entries[str(key)] = TextEntry(key=str(key), text=value)
        elif isinstance(value, dict):
            text = _first_string(value, TEXT_FIELDS)
            if text is None:
                continue
            metadata = {name: item for name, item in value.items() if name not in TEXT_FIELDS}
            entries[str(key)] = TextEntry(key=str(key), text=text, metadata=metadata)
    return TextCatalog(entries)


def _catalog_from_sequence(items: Any) -> TextCatalog:
    if not isinstance(items, list):
        raise ValueError("Catalog entries must be a list.")

    entries: OrderedDict[str, TextEntry] = OrderedDict()
    for index, item in enumerate(items):
        if isinstance(item, str):
            key = str(index)
            entries[key] = TextEntry(key=key, text=item)
            continue
        if not isinstance(item, dict):
            continue

        key = _first_string(item, KEY_FIELDS)
        text = _first_string(item, TEXT_FIELDS)
        if key is None or text is None:
            continue
        metadata = {name: value for name, value in item.items() if name not in KEY_FIELDS and name not in TEXT_FIELDS}
        entries[key] = TextEntry(key=key, text=text, metadata=metadata)
    return TextCatalog(entries)


def _first_string(data: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field_name in fields:
        value = data.get(field_name)
        if isinstance(value, str):
            return value
        if value is not None and field_name in KEY_FIELDS:
            return str(value)
    return None
