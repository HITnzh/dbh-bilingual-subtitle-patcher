from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import shutil
from typing import Any

from .patcher import PatchPlan, build_patch_plan

CATALOG_DIR = "catalog"
EXTRACTED_DIR = "extracted"
GENERATED_DIR = "generated"
REPORTS_DIR = "reports"
PATCH_PLAN_JSON = "patch-plan.json"
PREPARE_RESULT_JSON = "prepare-result.json"
BILINGUAL_CATALOG_JSON = "bilingual.json"


@dataclass(frozen=True)
class PrepareLayout:
    root: str
    catalog_dir: str
    extracted_dir: str
    generated_dir: str
    reports_dir: str
    catalog_path: str
    patch_plan_path: str
    prepare_result_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrepareResult:
    ok: bool
    layout: PrepareLayout
    patch_plan: dict[str, Any]
    created_dirs: list[str]
    written_files: list[str]
    errors: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "layout": self.layout.to_dict(),
            "patch_plan": self.patch_plan,
            "created_dirs": self.created_dirs,
            "written_files": self.written_files,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def build_prepare_layout(work_dir: Path | str) -> PrepareLayout:
    root = Path(work_dir)
    catalog_dir = root / CATALOG_DIR
    extracted_dir = root / EXTRACTED_DIR
    generated_dir = root / GENERATED_DIR
    reports_dir = root / REPORTS_DIR
    return PrepareLayout(
        root=str(root),
        catalog_dir=str(catalog_dir),
        extracted_dir=str(extracted_dir),
        generated_dir=str(generated_dir),
        reports_dir=str(reports_dir),
        catalog_path=str(catalog_dir / BILINGUAL_CATALOG_JSON),
        patch_plan_path=str(reports_dir / PATCH_PLAN_JSON),
        prepare_result_path=str(reports_dir / PREPARE_RESULT_JSON),
    )


def prepare_patch_workdir(
    game_dir: Path | str,
    *,
    catalog: Path | str,
    work_dir: Path | str,
    hash_manifest: Path | str | None = None,
    require_hash: bool = False,
    file_parser: Path | str | None = None,
    idx_detroit: Path | str | None = None,
    force: bool = False,
) -> PrepareResult:
    root = Path(work_dir)
    layout = build_prepare_layout(root)
    errors: list[str] = []
    warnings: list[str] = []
    created_dirs: list[str] = []
    written_files: list[str] = []

    if root.exists() and not root.is_dir():
        errors.append(f"Work path is not a directory: {root}")
    elif root.exists() and any(root.iterdir()) and not force:
        errors.append(f"Work directory is not empty: {root}. Use --force to reuse it.")

    plan: PatchPlan = build_patch_plan(
        game_dir,
        dry_run=True,
        catalog=catalog,
        work_dir=work_dir,
        hash_manifest=hash_manifest,
        require_hash=require_hash,
        file_parser=file_parser,
        idx_detroit=idx_detroit,
    )
    if plan.errors:
        errors.extend(plan.errors)

    if errors:
        return PrepareResult(
            ok=False,
            layout=layout,
            patch_plan=plan.to_dict(),
            created_dirs=created_dirs,
            written_files=written_files,
            errors=errors,
            warnings=warnings + plan.warnings,
        )

    for directory in (
        Path(layout.catalog_dir),
        Path(layout.extracted_dir),
        Path(layout.generated_dir),
        Path(layout.reports_dir),
    ):
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(directory))
        else:
            directory.mkdir(parents=True, exist_ok=True)

    catalog_target = Path(layout.catalog_path)
    shutil.copy2(Path(catalog), catalog_target)
    written_files.append(str(catalog_target))

    patch_plan_target = Path(layout.patch_plan_path)
    _write_json(patch_plan_target, plan.to_dict())
    written_files.append(str(patch_plan_target))

    result_target = Path(layout.prepare_result_path)
    written_files.append(str(result_target))
    final_result = PrepareResult(
        ok=True,
        layout=layout,
        patch_plan=plan.to_dict(),
        created_dirs=created_dirs,
        written_files=written_files,
        errors=errors,
        warnings=warnings + plan.warnings,
    )
    _write_json(result_target, final_result.to_dict())

    return final_result


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
