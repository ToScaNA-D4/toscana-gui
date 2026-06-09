from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def _infer_machine_project_root_from_cwd() -> Path | None:
    current = Path.cwd().expanduser()
    if current.name.lower() == "processed":
        return current
    for parent in current.parents:
        if parent.name.lower() == "processed":
            return parent
    return None


def machine_project_root() -> Path:
    configured = os.environ.get("TOSCANA_MACHINE_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    inferred = _infer_machine_project_root_from_cwd()
    if inferred is not None:
        return inferred
    raise RuntimeError(
        "Unable to determine the machine project root. Set TOSCANA_MACHINE_PROJECT_ROOT "
        "to the project root or the processed/ directory before launching the app."
    )
