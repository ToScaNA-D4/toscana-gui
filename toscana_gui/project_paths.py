from __future__ import annotations

from pathlib import Path

from toscana_gui.persistence import PROJECT_STATE_FILENAME, load_project_state

LEGACY_PROJECT_LAYOUT_VERSION = 1
SIBLING_PROJECT_LAYOUT_VERSION = 2
LEGACY_DATA_DIR = "processed"


def project_layout_version(project_root: Path) -> int:
    project_file = project_root / PROJECT_STATE_FILENAME
    if not project_file.exists():
        return LEGACY_PROJECT_LAYOUT_VERSION
    try:
        project_state = load_project_state(project_file)
    except Exception:
        return LEGACY_PROJECT_LAYOUT_VERSION
    try:
        return int(getattr(project_state.project, "layout_version", LEGACY_PROJECT_LAYOUT_VERSION))
    except Exception:
        return LEGACY_PROJECT_LAYOUT_VERSION


def uses_sibling_layout(project_root: Path, *, layout_version: int | None = None) -> bool:
    version = layout_version if layout_version is not None else project_layout_version(project_root)
    try:
        return int(version) >= SIBLING_PROJECT_LAYOUT_VERSION
    except Exception:
        return False


def project_data_root(project_root: Path, *, layout_version: int | None = None) -> Path:
    return project_root if uses_sibling_layout(project_root, layout_version=layout_version) else project_root / LEGACY_DATA_DIR


def project_data_path(project_root: Path, *parts: str | Path, layout_version: int | None = None) -> Path:
    data_root = project_data_root(project_root, layout_version=layout_version)
    return data_root.joinpath(*parts)
