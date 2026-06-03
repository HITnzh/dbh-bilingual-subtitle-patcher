from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from . import __version__
from .constants import BACKUP_MANIFEST, backup_root


@dataclass(frozen=True)
class BackupEntry:
    source: str
    backup: str
    size: int


@dataclass(frozen=True)
class BackupManifest:
    backup_id: str
    created_at: str
    tool_version: str
    game_dir: str
    files: list[BackupEntry]

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "created_at": self.created_at,
            "tool_version": self.tool_version,
            "game_dir": self.game_dir,
            "files": [entry.__dict__ for entry in self.files],
        }


def make_backup_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("%Y%m%dT%H%M%SZ")


def _assert_inside_game_dir(game_dir: Path, target: Path) -> None:
    root = game_dir.resolve()
    resolved = target.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"Refusing to operate outside game directory: {target}")


def create_backup(game_dir: Path | str, relative_files: list[str], *, backup_id: str | None = None) -> BackupManifest:
    root = Path(game_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Game directory does not exist: {root}")

    actual_backup_id = backup_id or make_backup_id()
    target_dir = backup_root(root) / actual_backup_id
    if target_dir.exists():
        raise FileExistsError(f"Backup already exists: {target_dir}")
    target_dir.mkdir(parents=True)

    entries: list[BackupEntry] = []
    for relative_name in relative_files:
        source = root / relative_name
        _assert_inside_game_dir(root, source)
        if not source.exists() or not source.is_file():
            continue

        backup_path = target_dir / relative_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup_path)
        entries.append(
            BackupEntry(
                source=relative_name,
                backup=str(backup_path.relative_to(target_dir)),
                size=source.stat().st_size,
            )
        )

    manifest = BackupManifest(
        backup_id=actual_backup_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        tool_version=__version__,
        game_dir=str(root),
        files=entries,
    )
    (target_dir / BACKUP_MANIFEST).write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return manifest


def list_backup_ids(game_dir: Path | str) -> list[str]:
    root = backup_root(Path(game_dir))
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def resolve_backup_id(game_dir: Path | str, backup_id: str | None = None) -> str:
    backups = list_backup_ids(game_dir)
    if not backups:
        raise FileNotFoundError("No backups created by this tool were found.")
    if backup_id in (None, "latest"):
        return backups[-1]
    if backup_id not in backups:
        raise FileNotFoundError(f"Backup not found: {backup_id}")
    return backup_id


def load_manifest(game_dir: Path | str, backup_id: str | None = None) -> BackupManifest:
    root = Path(game_dir)
    actual_backup_id = resolve_backup_id(root, backup_id)
    manifest_path = backup_root(root) / actual_backup_id / BACKUP_MANIFEST
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return BackupManifest(
        backup_id=data["backup_id"],
        created_at=data["created_at"],
        tool_version=data["tool_version"],
        game_dir=data["game_dir"],
        files=[BackupEntry(**entry) for entry in data["files"]],
    )


def restore_backup(game_dir: Path | str, backup_id: str | None = None, *, dry_run: bool = False) -> BackupManifest:
    root = Path(game_dir)
    manifest = load_manifest(root, backup_id)
    backup_dir = backup_root(root) / manifest.backup_id

    for entry in manifest.files:
        source = backup_dir / entry.backup
        target = root / entry.source
        _assert_inside_game_dir(root, target)
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return manifest
