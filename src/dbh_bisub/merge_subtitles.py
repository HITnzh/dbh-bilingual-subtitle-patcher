from __future__ import annotations

from dataclasses import dataclass
import re

TOKEN_RE = re.compile(
    r"(<[^>\r\n]+>|\{[^}\r\n]+\}|\[[A-Z0-9_:-]+\]|%[0-9.]*[A-Za-z]|\\[nrt])"
)
CUE_MARKER_RE = re.compile(r"\{\*[0-9]+\}")
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
DBH_LINE_BREAK = "{B}"
TIMED_CUE_SEPARATOR = " / "


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
    english_line = _clean_english_source(normalize_line(english))
    chinese_line = _clean_chinese_source(normalize_line(chinese))
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

    segmented_text = _merge_timed_cue_segments(english_line, chinese_line)
    if segmented_text is not None:
        return MergeResult(segmented_text, warnings)

    return MergeResult(_merge_visual_pair(english_line, chinese_line), warnings)


def _merge_timed_cue_segments(english: str, chinese: str) -> str | None:
    english_segments = _split_timed_cue_segments(english)
    chinese_segments = _split_timed_cue_segments(chinese)
    if english_segments is None or chinese_segments is None:
        return None
    english_prefix, english_parts = english_segments
    chinese_prefix, chinese_parts = chinese_segments
    if english_prefix.strip() or chinese_prefix.strip():
        return None
    if len(english_parts) != len(chinese_parts):
        return None
    english_markers = [marker for marker, _ in english_parts]
    chinese_markers = [marker for marker, _ in chinese_parts]
    if english_markers != chinese_markers:
        return None

    merged_parts = []
    for (marker, english_text), (_, chinese_text) in zip(english_parts, chinese_parts):
        merged_parts.append(_merge_timed_cue_segment(marker, english_text, chinese_text))
    return " ".join(part for part in merged_parts if part)


def _split_timed_cue_segments(text: str) -> tuple[str, list[tuple[str, str]]] | None:
    matches = list(CUE_MARKER_RE.finditer(text))
    if not matches:
        return None
    segments: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segments.append((match.group(0), text[match.end() : end]))
    return text[: matches[0].start()], segments


def _merge_timed_cue_segment(marker: str, english: str, chinese: str) -> str:
    english_text = english.strip()
    chinese_text = chinese.strip()
    if english_text and chinese_text:
        return f"{marker}{_merge_inline_pair(english_text, chinese_text)}"
    if english_text:
        return f"{marker}{_compact_visual_breaks(english_text)}"
    if chinese_text:
        return f"{marker}{_compact_visual_breaks(chinese_text)}"
    return marker


def _merge_inline_pair(english: str, chinese: str) -> str:
    english_text = _compact_visual_breaks(english)
    chinese_text = _compact_visual_breaks(chinese)
    if english_text and chinese_text:
        return f"{english_text}{TIMED_CUE_SEPARATOR}{chinese_text}"
    return english_text or chinese_text


def _merge_visual_pair(english: str, chinese: str) -> str:
    english_text = _compact_visual_breaks(english)
    chinese_text = _compact_visual_breaks(chinese)
    if english_text and chinese_text:
        return f"{english_text}{DBH_LINE_BREAK}{chinese_text}"
    return english_text or chinese_text


def _compact_visual_breaks(text: str) -> str:
    normalized = normalize_line(text)
    parts = []
    for line in normalized.replace("\n", DBH_LINE_BREAK).split(DBH_LINE_BREAK):
        line = line.strip()
        if line and (not parts or parts[-1] != line):
            parts.append(line)
    return " ".join(parts)


def _clean_english_source(text: str) -> str:
    return _keep_visual_lines_by_cjk(text, keep_cjk=False)


def _clean_chinese_source(text: str) -> str:
    return _keep_visual_lines_by_cjk(text, keep_cjk=True)


def _keep_visual_lines_by_cjk(text: str, *, keep_cjk: bool) -> str:
    parts = _visual_parts(text)
    if len(parts) < 2:
        return text

    preferred = [part for part in parts if bool(CJK_RE.search(part)) == keep_cjk]
    if not preferred or len(preferred) == len(parts):
        return text
    return DBH_LINE_BREAK.join(preferred)


def _visual_parts(text: str) -> list[str]:
    normalized = normalize_line(text)
    return [part.strip() for part in normalized.replace("\n", DBH_LINE_BREAK).split(DBH_LINE_BREAK) if part.strip()]
