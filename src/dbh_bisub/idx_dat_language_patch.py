from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import TextCatalog, load_catalog

LANGUAGE_MARKER_PREFIX = b"\x01\x03\x00\x00\x00"
LANGUAGE_MARKER_SUFFIX = b"\x12\x00\x00\x00"
LANGUAGE_CODE_ALIASES = {
    "CHT": "CHI",
    "TRADITIONAL_CHINESE": "CHI",
    "ZH_HANT": "CHI",
    "CHS": "SCH",
    "SIMPLIFIED_CHINESE": "SCH",
    "ZH_HANS": "SCH",
}
LANGUAGE_CODES = (
    "FRE",
    "ENG",
    "GER",
    "ITA",
    "SPA",
    "DUT",
    "POR",
    "SWE",
    "DAN",
    "NOR",
    "FIN",
    "RUS",
    "POL",
    "JPN",
    "KOR",
    "CHI",
    "GRE",
    "CZE",
    "HUN",
    "HRV",
    "MEX",
    "BRA",
    "TUR",
    "ARA",
    "SCH",
)


@dataclass(frozen=True)
class IdxDatLanguageFilePatch:
    relative_path: str
    source: str
    output: str
    language: str
    target_entries: int
    updated: int
    unchanged: int
    missing_in_source: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IdxDatLanguagePatchReport:
    source_entries: int
    language: str
    target_entries: int
    updated: int
    unchanged: int
    missing_in_source: int
    files_scanned: int
    files_written: int
    missing_language_files: list[str]
    files: list[IdxDatLanguageFilePatch]

    @property
    def ok(self) -> bool:
        return self.target_entries > 0 and (self.updated + self.unchanged) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source_entries": self.source_entries,
            "language": self.language,
            "target_entries": self.target_entries,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "missing_in_source": self.missing_in_source,
            "files_scanned": self.files_scanned,
            "files_written": self.files_written,
            "missing_language_files": self.missing_language_files,
            "files": [file.to_dict() for file in self.files],
        }


@dataclass(frozen=True)
class IdxDatLanguagePatchResult:
    output: str
    report: IdxDatLanguagePatchReport

    @property
    def ok(self) -> bool:
        return self.report.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": "idx_dat_language",
            "output": self.output,
            "report": self.report.to_dict(),
        }


def patch_idx_dat_language_tree(
    *,
    source: Path | str,
    extracted_dir: Path | str,
    output_dir: Path | str,
    language: str,
    report: Path | str | None = None,
) -> IdxDatLanguagePatchResult:
    source_catalog = load_catalog(source)
    extracted_root = Path(extracted_dir)
    generated_root = Path(output_dir)
    language_code = normalize_language_code(language)
    dat_files = _idx_dat_files(extracted_root)

    file_results: list[IdxDatLanguageFilePatch] = []
    missing_language_files: list[str] = []
    totals = {"target_entries": 0, "updated": 0, "unchanged": 0, "missing_in_source": 0}

    for dat_file in dat_files:
        relative = dat_file.relative_to(extracted_root)
        output_path = generated_root / relative
        patched_bytes, file_stats = _patch_dat_language_file(dat_file, source_catalog, language_code)
        for key in totals:
            totals[key] += file_stats[key]
        if not file_stats["language_found"]:
            missing_language_files.append(str(relative))
        if file_stats["updated"] > 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(patched_bytes)
            file_results.append(
                IdxDatLanguageFilePatch(
                    relative_path=str(relative),
                    source=str(dat_file),
                    output=str(output_path),
                    language=language_code,
                    target_entries=file_stats["target_entries"],
                    updated=file_stats["updated"],
                    unchanged=file_stats["unchanged"],
                    missing_in_source=file_stats["missing_in_source"],
                )
            )

    patch_report = IdxDatLanguagePatchReport(
        source_entries=source_catalog.count,
        language=language_code,
        target_entries=totals["target_entries"],
        updated=totals["updated"],
        unchanged=totals["unchanged"],
        missing_in_source=totals["missing_in_source"],
        files_scanned=len(dat_files),
        files_written=len(file_results),
        missing_language_files=missing_language_files,
        files=file_results,
    )

    if report is not None:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(patch_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return IdxDatLanguagePatchResult(output=str(generated_root), report=patch_report)


def normalize_language_code(language: str) -> str:
    code = language.strip().upper().replace("-", "_")
    code = LANGUAGE_CODE_ALIASES.get(code, code)
    if code not in LANGUAGE_CODES:
        supported = ", ".join(LANGUAGE_CODES)
        raise ValueError(f"Unsupported IDX language code: {language}. Supported codes: {supported}")
    return code


def _idx_dat_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted((path for path in root.rglob("*.dat") if path.is_file()), key=lambda path: str(path).lower())


def _patch_dat_language_file(
    path: Path,
    source_catalog: TextCatalog,
    language: str,
) -> tuple[bytes, dict[str, int | bool]]:
    data = path.read_bytes()
    ranges = _language_ranges(data)
    target_range = ranges.get(language)
    if target_range is None:
        return data, {
            "language_found": False,
            "target_entries": 0,
            "updated": 0,
            "unchanged": 0,
            "missing_in_source": 0,
        }

    block_start, block_end = target_range
    block, stats = _patch_language_block(data[block_start:block_end], source_catalog)
    patched = data[:block_start] + block + data[block_end:]
    stats["language_found"] = True
    return patched, stats


def _language_ranges(data: bytes) -> dict[str, tuple[int, int]]:
    ranges = _marker_language_ranges(data)
    for code, value_range in _record_header_language_ranges(data).items():
        ranges.setdefault(code, value_range)
    return ranges


def _marker_language_ranges(data: bytes) -> dict[str, tuple[int, int]]:
    markers: list[tuple[int, int, str]] = []
    for code in LANGUAGE_CODES:
        marker = LANGUAGE_MARKER_PREFIX + code.encode("ascii") + LANGUAGE_MARKER_SUFFIX
        start = 0
        while True:
            marker_start = data.find(marker, start)
            if marker_start < 0:
                break
            markers.append((marker_start, marker_start + len(marker), code))
            start = marker_start + 1

    markers.sort(key=lambda item: item[0])
    ranges: dict[str, tuple[int, int]] = {}
    for index, (_, marker_end, code) in enumerate(markers):
        next_start = markers[index + 1][0] if index + 1 < len(markers) else len(data)
        ranges[code] = (marker_end, next_start)
    return ranges


def _record_header_language_ranges(data: bytes) -> dict[str, tuple[int, int]]:
    headers: list[tuple[int, int, str]] = []
    position = 0
    while position < len(data):
        record = _read_record(data, position)
        if record is None:
            position += 1
            continue

        key, _, next_position = record
        if key in LANGUAGE_CODES:
            headers.append((position, next_position, key))
        position = next_position

    # This layout appears as many language-code records followed by normal
    # localization records. Requiring at least two headers avoids treating an
    # accidental short key in arbitrary DAT data as a whole language section.
    if len(headers) < 2:
        return {}

    ranges: dict[str, tuple[int, int]] = {}
    for index, (_, header_end, code) in enumerate(headers):
        next_start = headers[index + 1][0] if index + 1 < len(headers) else len(data)
        if header_end < next_start:
            ranges[code] = (header_end, next_start)
    return ranges


def _patch_language_block(block: bytes, source_catalog: TextCatalog) -> tuple[bytes, dict[str, int]]:
    position = 0
    stats = {"target_entries": 0, "updated": 0, "unchanged": 0, "missing_in_source": 0}
    replacements: list[tuple[int, int, bytes]] = []

    while position < len(block):
        record = _read_record(block, position)
        if record is None:
            position += 1
            continue

        key, value, next_position = record
        stats["target_entries"] += 1
        replacement = source_catalog.get_text(key)
        if not replacement:
            stats["missing_in_source"] += 1
            position = next_position
            continue

        replacement = _preserve_state_marker(value, replacement)
        if replacement == value:
            stats["unchanged"] += 1
        else:
            stats["updated"] += 1
            replacements.append((position, next_position, _encode_record(key, replacement)))
        position = next_position

    if not replacements:
        return block, stats

    output = bytearray()
    previous_end = 0
    for start, end, encoded in replacements:
        output.extend(block[previous_end:start])
        output.extend(encoded)
        previous_end = end
    output.extend(block[previous_end:])
    return bytes(output), stats


def _read_record(block: bytes, position: int) -> tuple[str, str, int] | None:
    if position + 8 > len(block):
        return None

    key_length = int.from_bytes(block[position : position + 4], "little")
    if key_length <= 0 or key_length > 512:
        return None
    key_start = position + 4
    key_end = key_start + key_length
    if key_end + 4 > len(block):
        return None

    key_bytes = block[key_start:key_end]
    try:
        key = key_bytes.decode("ascii")
    except UnicodeDecodeError:
        return None
    if not _looks_like_localization_key(key):
        return None

    value_length = int.from_bytes(block[key_end : key_end + 4], "little")
    value_start = key_end + 4
    value_end = value_start + value_length
    if value_length < 0 or value_length % 2 != 0 or value_end > len(block):
        return None
    try:
        value = block[value_start:value_end].decode("utf-16le")
    except UnicodeDecodeError:
        return None
    return key, value, value_end


def _encode_record(key: str, value: str) -> bytes:
    key_bytes = key.encode("ascii")
    value_bytes = value.encode("utf-16le")
    return (
        len(key_bytes).to_bytes(4, "little")
        + key_bytes
        + len(value_bytes).to_bytes(4, "little")
        + value_bytes
    )


def _looks_like_localization_key(key: str) -> bool:
    if not key:
        return False
    return all(char.isupper() or char.isdigit() or char == "_" for char in key)


def _preserve_state_marker(original: str, replacement: str) -> str:
    if original.startswith("{S}") and not replacement.startswith("{S}"):
        return "{S}" + replacement
    return replacement
