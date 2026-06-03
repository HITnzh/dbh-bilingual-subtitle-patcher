from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from .catalog import load_catalog

ENGLISH_TOKENS = {"en", "eng", "english", "enus", "enus"}
CHINESE_TOKENS = {
    "zh",
    "zho",
    "chi",
    "chs",
    "cht",
    "cn",
    "tw",
    "chinese",
    "schinese",
    "tchinese",
    "simplifiedchinese",
    "traditionalchinese",
    "zhcn",
    "zhtw",
    "zhhans",
    "zhhant",
}


@dataclass(frozen=True)
class CatalogFile:
    path: str
    relative_path: str
    file_name: str
    role: str
    entry_count: int | None
    readable: bool
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogDiscoveryReport:
    output_dir: str
    files: list[CatalogFile]
    english_candidates: list[str]
    chinese_candidates: list[str]
    recommended_english: str | None
    recommended_chinese: str | None
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output_dir": self.output_dir,
            "files": [file.to_dict() for file in self.files],
            "english_candidates": self.english_candidates,
            "chinese_candidates": self.chinese_candidates,
            "recommended_english": self.recommended_english,
            "recommended_chinese": self.recommended_chinese,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def discover_catalogs(output_dir: Path | str) -> CatalogDiscoveryReport:
    root = Path(output_dir)
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Output directory does not exist: {root}")
        return CatalogDiscoveryReport(str(root), [], [], [], None, None, errors, warnings)

    json_paths = sorted((path for path in root.rglob("*.json") if path.is_file()), key=lambda path: str(path).lower())
    if not json_paths:
        warnings.append("No JSON files were found in the output directory.")

    files = [_inspect_catalog_file(root, path) for path in json_paths]
    english_candidates = [file.relative_path for file in files if file.role == "english" and file.readable]
    chinese_candidates = [file.relative_path for file in files if file.role == "chinese" and file.readable]

    if not english_candidates:
        warnings.append("No English catalog candidate was found.")
    if not chinese_candidates:
        warnings.append("No Chinese catalog candidate was found.")

    return CatalogDiscoveryReport(
        output_dir=str(root),
        files=files,
        english_candidates=english_candidates,
        chinese_candidates=chinese_candidates,
        recommended_english=english_candidates[0] if english_candidates else None,
        recommended_chinese=chinese_candidates[0] if chinese_candidates else None,
        errors=errors,
        warnings=warnings,
    )


def _inspect_catalog_file(root: Path, path: Path) -> CatalogFile:
    errors: list[str] = []
    warnings: list[str] = []
    entry_count: int | None = None
    readable = False

    try:
        catalog = load_catalog(path)
        entry_count = catalog.count
        readable = True
        if catalog.count == 0:
            warnings.append("Catalog loaded but contains no entries.")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))

    relative_path = str(path.relative_to(root))
    return CatalogFile(
        path=str(path),
        relative_path=relative_path,
        file_name=path.name,
        role=infer_language_role(relative_path),
        entry_count=entry_count,
        readable=readable,
        errors=errors,
        warnings=warnings,
    )


def infer_language_role(path_text: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "", path_text.lower())
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", path_text.lower())))

    if tokens & ENGLISH_TOKENS or compact in ENGLISH_TOKENS:
        return "english"
    if tokens & CHINESE_TOKENS or compact in CHINESE_TOKENS:
        return "chinese"
    if any(
        token in compact
        for token in (
            "simplifiedchinese",
            "traditionalchinese",
            "chinesesimplified",
            "chinesetraditional",
            "schinese",
            "tchinese",
        )
    ):
        return "chinese"
    return "unknown"
