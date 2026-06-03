from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .constants import INDEX_FILE, PATCH_ARCHIVE
from .game_files import discover_archives, file_status

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class HashEntry:
    name: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HashManifest:
    schema_version: int
    version_id: str
    created_at: str
    files: list[HashEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "version_id": self.version_id,
            "created_at": self.created_at,
            "files": [entry.to_dict() for entry in self.files],
        }


@dataclass(frozen=True)
class HashMismatch:
    name: str
    expected_size: int | None
    actual_size: int | None
    expected_sha256: str | None
    actual_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HashComparisonReport:
    manifest_version_id: str
    matched: list[str]
    mismatched: list[HashMismatch]
    missing: list[str]
    extra: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors and not self.mismatched and not self.missing

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "manifest_version_id": self.manifest_version_id,
            "matched": self.matched,
            "mismatched": [item.to_dict() for item in self.mismatched],
            "missing": self.missing,
            "extra": self.extra,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def snapshot_hash_manifest(
    game_dir: Path | str,
    *,
    version_id: str = "local",
    include_patch_archive: bool = False,
) -> HashManifest:
    root = Path(game_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Game directory does not exist: {root}")

    files = _official_file_names(root, include_patch_archive=include_patch_archive)
    if not files:
        raise FileNotFoundError(f"No DBH files were found in: {root}")

    entries: list[HashEntry] = []
    for name in files:
        status = file_status(root / name, include_hash=True)
        if not status.exists or status.size is None or status.sha256 is None:
            continue
        entries.append(HashEntry(name=name, size=status.size, sha256=status.sha256))

    return HashManifest(
        schema_version=SCHEMA_VERSION,
        version_id=version_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        files=entries,
    )


def save_hash_manifest(path: Path | str, manifest: HashManifest) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_hash_manifest(path: Path | str) -> HashManifest:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    files = [HashEntry(name=item["name"], size=item["size"], sha256=item["sha256"]) for item in data.get("files", [])]
    return HashManifest(
        schema_version=int(data.get("schema_version", 0)),
        version_id=str(data.get("version_id", "")),
        created_at=str(data.get("created_at", "")),
        files=files,
    )


def compare_hash_manifest(
    game_dir: Path | str,
    manifest: HashManifest,
    *,
    include_patch_archive: bool = False,
) -> HashComparisonReport:
    root = Path(game_dir)
    errors: list[str] = []
    warnings: list[str] = []
    matched: list[str] = []
    mismatched: list[HashMismatch] = []
    missing: list[str] = []

    if manifest.schema_version != SCHEMA_VERSION:
        warnings.append(f"Unexpected hash manifest schema version: {manifest.schema_version}")
    if not root.exists() or not root.is_dir():
        errors.append(f"Game directory does not exist: {root}")
        return HashComparisonReport(manifest.version_id, matched, mismatched, missing, [], errors, warnings)

    expected = {entry.name: entry for entry in manifest.files}
    actual_names = _official_file_names(root, include_patch_archive=include_patch_archive)
    actual_statuses = {name: file_status(root / name, include_hash=True) for name in actual_names}

    for name, expected_entry in expected.items():
        actual = actual_statuses.get(name)
        if actual is None or not actual.exists:
            missing.append(name)
            continue
        if actual.size != expected_entry.size or actual.sha256 != expected_entry.sha256:
            mismatched.append(
                HashMismatch(
                    name=name,
                    expected_size=expected_entry.size,
                    actual_size=actual.size,
                    expected_sha256=expected_entry.sha256,
                    actual_sha256=actual.sha256,
                )
            )
            continue
        matched.append(name)

    extra = sorted(name for name in actual_statuses if name not in expected)
    if extra:
        warnings.append("Game directory contains DBH files not present in the manifest.")

    return HashComparisonReport(
        manifest_version_id=manifest.version_id,
        matched=matched,
        mismatched=mismatched,
        missing=missing,
        extra=extra,
        errors=errors,
        warnings=warnings,
    )


def _official_file_names(game_dir: Path, *, include_patch_archive: bool) -> list[str]:
    names: list[str] = []
    index = game_dir / INDEX_FILE
    if index.exists() and index.is_file():
        names.append(INDEX_FILE)
    for archive in discover_archives(game_dir):
        if archive.name == PATCH_ARCHIVE and not include_patch_archive:
            continue
        names.append(archive.name)
    return sorted(dict.fromkeys(names), key=str.lower)
