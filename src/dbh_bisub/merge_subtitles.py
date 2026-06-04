from __future__ import annotations

from dataclasses import dataclass
import re

TOKEN_RE = re.compile(
    r"(<[^>\r\n]+>|\{[^}\r\n]+\}|\[[A-Z0-9_:-]+\]|%[0-9.]*[A-Za-z]|\\[nrt])"
)
CUE_MARKER_RE = re.compile(r"\{\*[0-9]+\}")


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

    segmented_text = _merge_timed_cue_segments(english_line, chinese_line)
    if segmented_text is not None:
        return MergeResult(segmented_text, warnings)

    return MergeResult(f"{english_line}\n{chinese_line}", warnings)


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
        return f"{marker}{english_text}\n{chinese_text}"
    if english_text:
        return f"{marker}{english_text}"
    if chinese_text:
        return f"{marker}{chinese_text}"
    return marker
