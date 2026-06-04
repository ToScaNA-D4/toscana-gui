from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def contexts_root(project_root: Path) -> Path:
    return project_root / "processed" / "contexts"


def _to_project_relative_path(project_root: Path, path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(project_root.resolve(strict=False)).as_posix()
    except Exception:
        return str(path.resolve(strict=False))


def write_context_manifest(
    project_root: Path,
    *,
    context_id: str,
    payload: dict[str, Any],
) -> Path:
    target_dir = contexts_root(project_root) / str(context_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "context.json"
    target_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target_file


def project_relpath(project_root: Path, path: Path) -> str:
    return _to_project_relative_path(project_root, path)


def context_manifest_relpath(project_root: Path, manifest_file: Path) -> str:
    return project_relpath(project_root, manifest_file)


def resolve_project_path(project_root: Path, path_ref: str | Path) -> Path:
    path = Path(path_ref).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve(strict=False)


def load_context_manifest(project_root: Path, manifest_ref: str | Path) -> dict[str, Any] | None:
    try:
        manifest_path = resolve_project_path(project_root, manifest_ref)
    except Exception:
        return None
    if not manifest_path.exists() or not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
