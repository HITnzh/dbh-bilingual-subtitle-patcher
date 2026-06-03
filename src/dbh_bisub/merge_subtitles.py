from __future__ import annotations

from dataclasses import dataclass
import re

TOKEN_RE = re.compile(
    r"(<[^>\r\n]+>|\{[^}\r\n]+\}|\[[A-Z0-9_:-]+\]|%[0-9.]*[A-Za-z]|\\[nrt])"
)


@dataclass(frozen=True)
class MergeResult:
    text: str
    warnings: list[str]


def normalize_line(text: str | None) -> str:
    if text is None:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def extract_control_tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def merge_bilingual_text(english: str | None, chinese: str | None) -> MergeResult:
    english_line = normalize_line(english)
    chinese_line = normalize_line(chinese)
    warnings: list[str] = []

    if not english_line and not chinese_line:
        return MergeResult("", warnings)
    if not english_line:
        warnings.append("Missing English text; using Chinese only.")
        return MergeResult(chinese_line, warnings)
    if not chinese_line:
        warnings.append("Missing Chinese text; using English only.")
        return MergeResult(english_line, warnings)

    english_tokens = extract_control_tokens(english_line)
    chinese_tokens = extract_control_tokens(chinese_line)
    if english_tokens != chinese_tokens:
        warnings.append("Control tokens differ between English and Chinese text.")

    return MergeResult(f"{english_line}\n{chinese_line}", warnings)
