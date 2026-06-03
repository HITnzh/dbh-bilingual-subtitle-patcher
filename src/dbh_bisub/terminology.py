from __future__ import annotations

from collections import Counter, OrderedDict
import csv
from dataclasses import asdict, dataclass
import io
from pathlib import Path
from typing import Any

from .catalog import TextCatalog, TextEntry

SOURCE_COLUMNS = ("source", "from", "traditional", "original")
TARGET_COLUMNS = ("target", "to", "simplified", "replacement")
NOTE_COLUMNS = ("note", "notes", "comment")


@dataclass(frozen=True)
class TermRule:
    source: str
    target: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TermApplication:
    text: str
    replacements: Counter[str]


@dataclass(frozen=True)
class TerminologyReport:
    rules_loaded: int
    rules_matched: int
    replacements: int
    by_source: dict[str, int]

    @property
    def changed(self) -> bool:
        return self.replacements > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_loaded": self.rules_loaded,
            "rules_matched": self.rules_matched,
            "replacements": self.replacements,
            "by_source": self.by_source,
        }


def load_terminology(path: Path | str) -> list[TermRule]:
    source = Path(path)
    raw = source.read_text(encoding="utf-8-sig")
    filtered = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("#"))
    reader = csv.DictReader(io.StringIO(filtered))
    if reader.fieldnames is None:
        return []

    rules: list[TermRule] = []
    for row_number, row in enumerate(reader, start=2):
        source_text = _first_present(row, SOURCE_COLUMNS)
        target_text = _first_present(row, TARGET_COLUMNS)
        note = _first_present(row, NOTE_COLUMNS) or ""
        if not source_text and not target_text:
            continue
        if not source_text or not target_text:
            raise ValueError(f"Invalid terminology row {row_number}: source and target are required.")
        rules.append(TermRule(source=source_text, target=target_text, note=note))
    return rules


def apply_terminology(text: str, rules: list[TermRule]) -> TermApplication:
    replacements: Counter[str] = Counter()
    result = text
    for rule in sorted(rules, key=lambda item: len(item.source), reverse=True):
        if not rule.source:
            continue
        count = result.count(rule.source)
        if count == 0:
            continue
        result = result.replace(rule.source, rule.target)
        replacements[rule.source] += count
    return TermApplication(text=result, replacements=replacements)


def apply_terminology_to_catalog(catalog: TextCatalog, rules: list[TermRule]) -> tuple[TextCatalog, TerminologyReport]:
    entries: OrderedDict[str, TextEntry] = OrderedDict()
    totals: Counter[str] = Counter()

    for key, entry in catalog.entries.items():
        application = apply_terminology(entry.text, rules)
        totals.update(application.replacements)
        entries[key] = TextEntry(key=entry.key, text=application.text, metadata=entry.metadata)

    report = TerminologyReport(
        rules_loaded=len(rules),
        rules_matched=sum(1 for value in totals.values() if value > 0),
        replacements=sum(totals.values()),
        by_source=dict(sorted(totals.items())),
    )
    return TextCatalog(entries), report


def _first_present(row: dict[str, str | None], columns: tuple[str, ...]) -> str | None:
    normalized = {key.strip().lower(): value for key, value in row.items() if key is not None}
    for column in columns:
        value = normalized.get(column)
        if value is not None and value.strip():
            return value.strip()
    return None
