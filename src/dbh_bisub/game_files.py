from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import re
from typing import Any

from .constants import INDEX_FILE, PATCH_ARCHIVE, backup_root

ARCHIVE_RE = re.compile(r"^BigFile_PC\.d\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class FileStatus:
    name: str
    exists: bool
    size: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class GameDirectoryReport:
    game_dir: str
    exists: bool
    index: FileStatus
    archives: list[FileStatus]
    patch_archive: FileStatus
    backups: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_status(path: Path, *, include_hash: bool = False) -> FileStatus:
    if not path.exists():
        return FileStatus(name=path.name, exists=False)
    if not path.is_file():
        return FileStatus(name=path.name, exists=False)
    return FileStatus(
        name=path.name,
        exists=True,
        size=path.stat().st_size,
        sha256=sha256_file(path) if include_hash else None,
    )


def discover_archives(game_dir: Path, *, include_hash: bool = False) -> list[FileStatus]:
    if not game_dir.exists() or not game_dir.is_dir():
        return []
    paths = sorted(
        (path for path in game_dir.iterdir() if path.is_file() and ARCHIVE_RE.match(path.name)),
        key=lambda path: path.name.lower(),
    )
    return [file_status(path, include_hash=include_hash) for path in paths]


def discover_backups(game_dir: Path) -> list[str]:
    root = backup_root(game_dir)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def inspect_game_dir(game_dir: Path | str, *, include_hashes: bool = False) -> GameDirectoryReport:
    path = Path(game_dir)
    errors: list[str] = []
    warnings: list[str] = []

    exists = path.exists() and path.is_dir()
    index = file_status(path / INDEX_FILE, include_hash=include_hashes) if exists else FileStatus(INDEX_FILE, False)
    archives = discover_archives(path, include_hash=include_hashes)
    patch_archive = file_status(path / PATCH_ARCHIVE, include_hash=include_hashes) if exists else FileStatus(PATCH_ARCHIVE, False)
    backups = discover_backups(path) if exists else []

    if not exists:
        errors.append(f"Game directory does not exist or is not a directory: {path}")
    if exists and not index.exists:
        errors.append(f"Missing required index file: {INDEX_FILE}")
    if exists and not archives:
        warnings.append("No BigFile_PC.d* archive files were found.")
    if patch_archive.exists:
        warnings.append(f"{PATCH_ARCHIVE} already exists; it may be from another mod or previous patch.")

    return GameDirectoryReport(
        game_dir=str(path),
        exists=exists,
        index=index,
        archives=archives,
        patch_archive=patch_archive,
        backups=backups,
        errors=errors,
        warnings=warnings,
    )
