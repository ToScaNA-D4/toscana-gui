from __future__ import annotations

from pathlib import Path
from typing import Literal

from toscana_gui.project_paths import SIBLING_PROJECT_LAYOUT_VERSION
from toscana_gui.project_paths import project_data_path
from toscana_gui.persistence import (
    ProjectState,
    RecentProjectEntry,
    create_project_state,
    load_project_state,
    now_iso,
    save_app_state,
    save_project_state,
)

PROJECT_BOOTSTRAP_DIRS: tuple[str, ...] = (
    "parfiles",
    "regdata",
    "qspdata",
    "logfiles",
    "background",
    "normalization",
    "self_scattering",
    "ft",
    "bft",
    "contexts",
)

WorkspaceTab = Literal[
    "project",
    "numors",
    "background",
    "normalization",
    "self",
    "ft",
    "bft",
    "run_history",
    "help",
]

WORKSPACE_TAB_ORDER: tuple[WorkspaceTab, ...] = (
    "project",
    "numors",
    "background",
    "normalization",
    "self",
    "ft",
    "bft",
    "run_history",
    "help",
)

WORKSPACE_TAB_TITLES: dict[WorkspaceTab, str] = {
    "project": "Project",
    "numors": "Numors",
    "background": "Background",
    "normalization": "Normalization",
    "self": "Self",
    "ft": "FT",
    "bft": "BFT",
    "run_history": "Run History",
    "help": "Help / About",
}

STATIC_PLOT_WARNING = (
    "Plots could not be recomputed in this session. Saved outputs and logs are "
    "available; any displayed plots are static from a past session."
)


def normalize_workspace_tab(tab_name: str | None) -> WorkspaceTab:
    legacy_tab_map: dict[str, WorkspaceTab] = {
        "d4_reduction": "numors",
    }
    if tab_name in legacy_tab_map:
        return legacy_tab_map[tab_name]
    if tab_name in WORKSPACE_TAB_ORDER:
        return tab_name
    return "project"


def validate_recent_entry(entry: RecentProjectEntry) -> RecentProjectEntry:
    project_file = Path(entry.project_file)
    if not project_file.exists():
        return RecentProjectEntry(
            project_name=entry.project_name,
            project_file=entry.project_file,
            last_opened_at=entry.last_opened_at,
            status="missing",
            warning="Project file could not be found.",
        )

    try:
        project_state = load_project_state(project_file)
    except Exception as exc:
        return RecentProjectEntry(
            project_name=entry.project_name,
            project_file=entry.project_file,
            last_opened_at=entry.last_opened_at,
            status="invalid",
            warning=f"Project file is invalid: {exc}",
        )

    return RecentProjectEntry(
        project_name=project_state.project.name,
        project_file=str(project_file.resolve()),
        last_opened_at=entry.last_opened_at,
        status="ok",
        warning=None,
    )


def persist_app_state(app_state_path: Path, app_state) -> None:
    save_app_state(app_state_path, app_state)


def remember_project(app_state, project_state: ProjectState, project_file: Path) -> None:
    app_state.remember_project(
        RecentProjectEntry(
            project_name=project_state.project.name,
            project_file=str(project_file.resolve()),
            last_opened_at=now_iso(),
            status="ok",
            warning=None,
        )
    )


def derive_project_name(project_root: Path) -> str:
    if project_root.name.lower() == "processed":
        return project_root.parent.name.strip() or "project"
    return project_root.name.strip() or "project"


def ensure_project_bootstrap_dirs(project_root: Path, *, layout_version: int) -> None:
    for dirname in PROJECT_BOOTSTRAP_DIRS:
        project_data_path(project_root, dirname, layout_version=layout_version).mkdir(
            parents=True,
            exist_ok=True,
        )


def create_new_project(
    project_name: str,
    project_root: Path,
    *,
    layout_version: int = SIBLING_PROJECT_LAYOUT_VERSION,
) -> tuple[ProjectState, Path]:
    project_state = create_project_state(
        project_name,
        last_top_level_tab="project",
        layout_version=layout_version,
    )
    project_file = project_root / "toscana-project.json"
    save_project_state(project_file, project_state)
    ensure_project_bootstrap_dirs(project_root, layout_version=layout_version)
    return project_state, project_file.resolve()


def bootstrap_project(
    project_root: Path,
    *,
    layout_version: int = SIBLING_PROJECT_LAYOUT_VERSION,
) -> tuple[ProjectState, Path, bool]:
    project_file = project_root / "toscana-project.json"
    if project_file.exists():
        return load_project_state(project_file), project_file.resolve(), False

    project_name = derive_project_name(project_root)
    project_state, resolved_project_file = create_new_project(
        project_name,
        project_root,
        layout_version=layout_version,
    )
    return project_state, resolved_project_file, True


def save_project_file(project_file: Path, project_state: ProjectState) -> None:
    save_project_state(project_file, project_state)


def project_has_saved_outputs(project_state: ProjectState) -> bool:
    for record in project_state.runs:
        output_paths = record.output_paths
        if any(
            [
                output_paths.stdout_file,
                output_paths.logfile,
                output_paths.reg_file,
                output_paths.adat_file,
                output_paths.qdat_file,
            ]
        ):
            return True
    return False


def restore_project_resume_state(project_state: ProjectState) -> tuple[WorkspaceTab, bool]:
    updated = False
    restored_tab = normalize_workspace_tab(project_state.resume.last_top_level_tab)
    if restored_tab != project_state.resume.last_top_level_tab:
        project_state.resume.last_top_level_tab = restored_tab
        updated = True

    if project_has_saved_outputs(project_state):
        if (
            not project_state.resume.has_static_plot_warning
            or not project_state.resume.static_plot_warning
        ):
            project_state.resume.has_static_plot_warning = True
            project_state.resume.static_plot_warning = STATIC_PLOT_WARNING
            updated = True

    return restored_tab, updated
