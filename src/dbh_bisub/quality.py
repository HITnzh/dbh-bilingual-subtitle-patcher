from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .catalog import TextCatalog
from .merge_subtitles import extract_control_tokens, normalize_line

DEFAULT_MAX_LINES = 2
DEFAULT_MAX_LINE_CHARS = 84
DEFAULT_MAX_TOTAL_CHARS = 160


@dataclass(frozen=True)
class QualityIssue:
    key: str
    level: str
    code: str
    message: str
    value: int | str | None = None
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogQualityReport:
    entries: int
    issue_count: int
    warnings: int
    errors: int
    max_lines: int
    max_line_chars: int
    max_total_chars: int
    longest_line_chars: int
    longest_total_chars: int
    issues_by_code: dict[str, int]
    issues: list[QualityIssue]

    @property
    def ok(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "entries": self.entries,
            "issue_count": self.issue_count,
            "warnings": self.warnings,
            "errors": self.errors,
            "max_lines": self.max_lines,
            "max_line_chars": self.max_line_chars,
            "max_total_chars": self.max_total_chars,
            "longest_line_chars": self.longest_line_chars,
            "longest_total_chars": self.longest_total_chars,
            "issues_by_code": self.issues_by_code,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def inspect_catalog_quality(
    catalog: TextCatalog,
    *,
    max_lines: int = DEFAULT_MAX_LINES,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> CatalogQualityReport:
    issues: list[QualityIssue] = []
    longest_line_chars = 0
    longest_total_chars = 0

    for key, entry in catalog.entries.items():
        text = normalize_line(entry.text)
        lines = text.split("\n") if text else []
        line_lengths = [len(line) for line in lines]
        total_chars = sum(line_lengths)
        longest_line = max(line_lengths, default=0)
        longest_line_chars = max(longest_line_chars, longest_line)
        longest_total_chars = max(longest_total_chars, total_chars)

        if not text:
            issues.append(QualityIssue(key, "warning", "empty_text", "Entry text is empty."))
            continue
        if len(lines) > max_lines:
            issues.append(
                QualityIssue(
                    key,
                    "warning",
                    "too_many_lines",
                    f"Entry has {len(lines)} visual lines.",
                    value=len(lines),
                    limit=max_lines,
                )
            )
        if longest_line > max_line_chars:
            issues.append(
                QualityIssue(
                    key,
                    "warning",
                    "line_too_long",
                    f"Longest line has {longest_line} characters.",
                    value=longest_line,
                    limit=max_line_chars,
                )
            )
        if total_chars > max_total_chars:
            issues.append(
                QualityIssue(
                    key,
                    "warning",
                    "text_too_long",
                    f"Entry has {total_chars} total characters.",
                    value=total_chars,
                    limit=max_total_chars,
                )
            )

        token_issues = _inspect_control_tokens(key, lines)
        issues.extend(token_issues)

    by_level = Counter(issue.level for issue in issues)
    by_code = Counter(issue.code for issue in issues)
    return CatalogQualityReport(
        entries=catalog.count,
        issue_count=len(issues),
        warnings=by_level["warning"],
        errors=by_level["error"],
        max_lines=max_lines,
        max_line_chars=max_line_chars,
        max_total_chars=max_total_chars,
        longest_line_chars=longest_line_chars,
        longest_total_chars=longest_total_chars,
        issues_by_code=dict(sorted(by_code.items())),
        issues=issues,
    )


def _inspect_control_tokens(key: str, lines: list[str]) -> list[QualityIssue]:
    if len(lines) < 2:
        return []
    first_line_tokens = extract_control_tokens(lines[0])
    issues: list[QualityIssue] = []
    for index, line in enumerate(lines[1:], start=2):
        tokens = extract_control_tokens(line)
        if tokens != first_line_tokens:
            issues.append(
                QualityIssue(
                    key,
                    "warning",
                    "control_tokens_differ",
                    f"Control tokens differ between line 1 and line {index}.",
                    value=f"{first_line_tokens} != {tokens}",
                )
            )
    return issues
