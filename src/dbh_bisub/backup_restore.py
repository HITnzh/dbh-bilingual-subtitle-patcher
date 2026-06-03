from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from . import __version__
from .constants import BACKUP_MANIFEST, INDEX_FILE, PATCH_ARCHIVE, backup_root

DEFAULT_BACKUP_FILES = [INDEX_FILE, PATCH_ARCHIVE]


@dataclass(frozen=True)
class BackupEntry:
    source: str
    backup: str
    size: int


@dataclass(frozen=True)
class BackupPlan:
    backup_id: str
    game_dir: str
    target_dir: str
    requested_files: list[str]
    files_to_backup: list[BackupEntry]
    missing_files: list[str]
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "backup_id": self.backup_id,
            "game_dir": self.game_dir,
            "target_dir": self.target_dir,
            "requested_files": self.requested_files,
            "files_to_backup": [entry.__dict__ for entry in self.files_to_backup],
            "missing_files": self.missing_files,
            "errors": self.errors,
            "warnings": self.warnings,
        }


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


def plan_backup(game_dir: Path | str, relative_files: list[str] | None = None, *, backup_id: str | None = None) -> BackupPlan:
    root = Path(game_dir)
    actual_backup_id = backup_id or make_backup_id()
    requested_files = list(relative_files or DEFAULT_BACKUP_FILES)
    target_dir = backup_root(root) / actual_backup_id
    files_to_backup: list[BackupEntry] = []
    missing_files: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists() or not root.is_dir():
        errors.append(f"Game directory does not exist: {root}")
        return BackupPlan(actual_backup_id, str(root), str(target_dir), requested_files, files_to_backup, missing_files, errors, warnings)
    if target_dir.exists():
        errors.append(f"Backup already exists: {target_dir}")

    for relative_name in requested_files:
        source = root / relative_name
        try:
            _assert_inside_game_dir(root, source)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not source.exists() or not source.is_file():
            missing_files.append(relative_name)
            continue
        files_to_backup.append(
            BackupEntry(
                source=relative_name,
                backup=relative_name,
                size=source.stat().st_size,
            )
        )

    if not files_to_backup:
        errors.append("No requested files exist to back up.")
    if missing_files:
        warnings.append("Some requested files do not exist and will be skipped.")

    return BackupPlan(actual_backup_id, str(root), str(target_dir), requested_files, files_to_backup, missing_files, errors, warnings)


def create_backup(game_dir: Path | str, relative_files: list[str], *, backup_id: str | None = None) -> BackupManifest:
    root = Path(game_dir)
    plan = plan_backup(root, relative_files, backup_id=backup_id)
    if plan.errors:
        raise FileNotFoundError("; ".join(plan.errors))

    target_dir = Path(plan.target_dir)
    target_dir.mkdir(parents=True)

    entries: list[BackupEntry] = []
    for planned_entry in plan.files_to_backup:
        relative_name = planned_entry.source
        source = root / relative_name
        _assert_inside_game_dir(root, source)

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
        backup_id=plan.backup_id,
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
