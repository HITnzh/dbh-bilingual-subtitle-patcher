from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .catalog import TextCatalog, load_catalog


@dataclass(frozen=True)
class IdxTextFilePatch:
    relative_path: str
    source: str
    output: str
    target_entries: int
    updated: int
    unchanged: int
    skipped: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IdxTextInjectionReport:
    source_entries: int
    target_entries: int
    updated: int
    unchanged: int
    skipped: int
    files_scanned: int
    files_written: int
    missing_in_target: list[str]
    missing_in_source: list[str]
    files: list[IdxTextFilePatch]

    @property
    def ok(self) -> bool:
        return self.target_entries > 0 and (self.updated + self.unchanged) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source_entries": self.source_entries,
            "target_entries": self.target_entries,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "files_scanned": self.files_scanned,
            "files_written": self.files_written,
            "missing_in_target": self.missing_in_target,
            "missing_in_source": self.missing_in_source,
            "files": [file.to_dict() for file in self.files],
        }


@dataclass(frozen=True)
class IdxTextInjectionResult:
    output: str
    report: IdxTextInjectionReport

    @property
    def ok(self) -> bool:
        return self.report.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "mode": "idx_text",
            "output": self.output,
            "report": self.report.to_dict(),
        }


def inject_idx_text_tree(
    *,
    source: Path | str,
    extracted_dir: Path | str,
    output_dir: Path | str,
    report: Path | str | None = None,
) -> IdxTextInjectionResult:
    source_catalog = load_catalog(source)
    extracted_root = Path(extracted_dir)
    generated_root = Path(output_dir)
    text_files = _idx_text_files(extracted_root)

    seen_keys: set[str] = set()
    missing_in_source: set[str] = set()
    file_results: list[IdxTextFilePatch] = []
    totals = {"target_entries": 0, "updated": 0, "unchanged": 0, "skipped": 0}

    for text_file in text_files:
        relative = text_file.relative_to(extracted_root)
        output_path = generated_root / relative
        patched_lines, file_stats = _patch_text_file(text_file, source_catalog, seen_keys, missing_in_source)
        for key in totals:
            totals[key] += file_stats[key]
        if file_stats["updated"] > 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("".join(patched_lines), encoding="utf-8")
            file_results.append(
                IdxTextFilePatch(
                    relative_path=str(relative),
                    source=str(text_file),
                    output=str(output_path),
                    target_entries=file_stats["target_entries"],
                    updated=file_stats["updated"],
                    unchanged=file_stats["unchanged"],
                    skipped=file_stats["skipped"],
                )
            )

    missing_in_target = [key for key in source_catalog.keys() if key not in seen_keys]
    injection_report = IdxTextInjectionReport(
        source_entries=source_catalog.count,
        target_entries=totals["target_entries"],
        updated=totals["updated"],
        unchanged=totals["unchanged"],
        skipped=totals["skipped"],
        files_scanned=len(text_files),
        files_written=len(file_results),
        missing_in_target=missing_in_target,
        missing_in_source=sorted(missing_in_source),
        files=file_results,
    )

    if report is not None:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(injection_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return IdxTextInjectionResult(output=str(generated_root), report=injection_report)


def has_idx_text_files(path: Path | str) -> bool:
    return bool(_idx_text_files(Path(path)))


def _idx_text_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        (path for path in root.rglob("*.txt") if path.is_file()),
        key=lambda path: str(path).lower(),
    )


def _patch_text_file(
    path: Path,
    source_catalog: TextCatalog,
    seen_keys: set[str],
    missing_in_source: set[str],
) -> tuple[list[str], dict[str, int]]:
    stats = {"target_entries": 0, "updated": 0, "unchanged": 0, "skipped": 0}
    patched: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for line in file:
            body, newline = _split_newline(line)
            if "=" not in body:
                patched.append(line)
                stats["skipped"] += 1
                continue
            key, current = body.split("=", 1)
            if not key:
                patched.append(line)
                stats["skipped"] += 1
                continue

            stats["target_entries"] += 1
            seen_keys.add(key)
            replacement = source_catalog.get_text(key)
            if replacement == "":
                missing_in_source.add(key)
                patched.append(line)
                continue

            encoded = encode_idx_text_value(replacement)
            if encoded == current:
                patched.append(line)
                stats["unchanged"] += 1
            else:
                patched.append(f"{key}={encoded}{newline}")
                stats["updated"] += 1
    return patched, stats


def encode_idx_text_value(value: str) -> str:
    return (
        value.replace("=", "[p]")
        .replace("\r\n", "[rn]")
        .replace("\n\r", "[nr]")
        .replace("\r", "[r]")
        .replace("\n", "[n]")
    )


def _split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""
