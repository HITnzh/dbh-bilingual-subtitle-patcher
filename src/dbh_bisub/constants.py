from pathlib import Path

INDEX_FILE = "BigFile_PC.idx"
PATCH_ARCHIVE = "BigFile_PC.d30"
BACKUP_ROOT = ".dbh-bisub-backups"
BACKUP_MANIFEST = "manifest.json"


def backup_root(game_dir: Path) -> Path:
    return game_dir / BACKUP_ROOT
