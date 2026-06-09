from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


def machine_project_root() -> Path:
    configured = os.environ.get("TOSCANA_MACHINE_PROJECT_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser()
    return REPO_ROOT / "Projects"
