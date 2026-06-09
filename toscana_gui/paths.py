from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def _normalize_machine_project_root(candidate: Path) -> Path:
    resolved = candidate.expanduser()
    if resolved.name.lower() == "processed":
        return resolved.parent
    return resolved


def _infer_machine_project_root_from_cwd() -> Path | None:
    current = Path.cwd().expanduser()
    if current.name.lower() == "processed":
        return current.parent
    for parent in current.parents:
        if parent.name.lower() == "processed":
            return parent.parent
    return None


def machine_project_root() -> Path:
    configured = os.environ.get("TOSCANA_MACHINE_PROJECT_ROOT", "").strip()
    if configured:
        return _normalize_machine_project_root(Path(configured))
    inferred = _infer_machine_project_root_from_cwd()
    if inferred is not None:
        return inferred
    raise RuntimeError(
        "Unable to determine the machine project root. Set TOSCANA_MACHINE_PROJECT_ROOT "
        "to the project root or the processed/ directory before launching the app."
    )
