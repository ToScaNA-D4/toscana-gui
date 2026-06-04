from __future__ import annotations

import subprocess
from pathlib import Path

import panel as pn

from toscana_gui.numors.controller import NumorsControllerMixin
from toscana_gui.background.controller import BackgroundControllerMixin
from toscana_gui.normalization.controller import NormalizationControllerMixin
from toscana_gui.self_scattering.controller import SelfScatteringControllerMixin
from toscana_gui.ft.controller import FTControllerMixin
from toscana_gui.bft.controller import BFTControllerMixin
from toscana_gui.paths import REPO_ROOT
from toscana_gui.persistence import (
    APP_STATE_FILENAME,
    AppState,
    ProjectState,
    load_app_state,
)
from toscana_gui.projects.controller import ProjectSessionControllerMixin
from toscana_gui.projects.tasks import WorkspaceTab
from toscana_gui.ui import runtime as ui_runtime
from toscana_gui.ui.callbacks import bind_shell_callbacks
from toscana_gui.ui.theme import configure_panel
from toscana_gui.ui.widgets import initialize_shell_widgets

APP_STATE_PATH = REPO_ROOT / APP_STATE_FILENAME


class ToScaNAShell(
    ProjectSessionControllerMixin,
    NumorsControllerMixin,
    BackgroundControllerMixin,
    NormalizationControllerMixin,
    SelfScatteringControllerMixin,
    FTControllerMixin,
    BFTControllerMixin,
):
    def __init__(self) -> None:
        configure_panel()

        self.current_screen = "landing"
        self.workspace_entrypoint = "No action selected yet."
        self.workspace_result: str | None = None
        self.pending_navigation_action: str | None = None
        self.current_project_root: Path | None = None
        self.current_project_file: Path | None = None
        self.current_project_state: ProjectState | None = None
        self.current_project_dirty = False
        self.current_top_level_tab: WorkspaceTab = "project"
        self.operation_in_progress = False
        self._suspend_dirty_tracking = False
        self._suspend_numors_events = False
        self._suspend_background_events = False
        self._suspend_normalization_events = False
        self._suspend_self_scattering_events = False
        self._suspend_ft_events = False
        self._numors_run_process: subprocess.Popen | None = None
        self._numors_run_poll = None
        self._numors_active_run_id: str | None = None
        self._numors_result_file: Path | None = None
        self._background_run_process: subprocess.Popen | None = None
        self._background_run_poll = None
        self._background_active_run_id: str | None = None
        self._background_result_file: Path | None = None
        self._pending_background_import_path: Path | None = None
        self._pending_normalization_import_paths: dict[str, Path] | None = None
        self._pending_normalization_adopt: dict[str, str] | None = None
        self._background_cached_measurement = None
        self._background_cached_artifact_path: str | None = None
        self._background_cached_artifact_mtime: float | None = None
        self._run_history_block_viewers: dict[str, dict[str, object]] = {}
        self._workspace_loading_depth = 0
        self._workspace_loading_message_text = ""
        self._ft_soq_cache: dict[str, object] = {}
        self._ft_soq_current: dict[str, object] | None = None
        self._ft_soq_selected_path: Path | None = None
        self.app_state: AppState = load_app_state(APP_STATE_PATH)
        self._toast_last_by_key: dict[str, str] = {}

        initialize_shell_widgets(self)
        bind_shell_callbacks(self)
        self._render_current_screen()

    def _render_current_screen(self) -> None:
        ui_runtime.render_current_screen(self)

    def _refresh_interaction_states(self) -> None:
        ui_runtime.refresh_interaction_states(self)

    def _refresh_workspace_button_states(self) -> None:
        ui_runtime.refresh_workspace_button_states(self)

    def _show_workspace_blocked_message(self) -> None:
        ui_runtime.show_workspace_blocked_message(self)

    def _clear_workspace_message(self) -> None:
        ui_runtime.clear_workspace_message(self)

    def _show_success_toast(self, message: str) -> None:
        ui_runtime.show_success_toast(self, message)

    def _show_info_toast(self, message: str) -> None:
        ui_runtime.show_info_toast(self, message)

    def _show_warning_toast(self, message: str) -> None:
        ui_runtime.show_warning_toast(self, message)

    def _show_error_toast(self, message: str) -> None:
        ui_runtime.show_error_toast(self, message)

    def _show_toast_once(
        self,
        key: str,
        *,
        level: str,
        message: str,
        persistent: bool | None = None,
    ) -> None:
        signature = f"{level}:{message}"
        if self._toast_last_by_key.get(key) == signature:
            return
        self._toast_last_by_key[key] = signature
        ui_runtime.show_toast(self, level=level, message=message, persistent=persistent)

    def _reset_toast_once(self) -> None:
        self._toast_last_by_key = {}

    def _clear_success_toast_if_current(self, token: int) -> None:
        ui_runtime.clear_success_toast_if_current(self, token)

    def _clear_run_history_viewers(self) -> None:
        self._run_history_block_viewers = {}

    def _begin_workspace_loading(self, message: str = "Loading...") -> None:
        ui_runtime.begin_workspace_loading(self, message)

    def _end_workspace_loading(self, *, defer: bool = False) -> None:
        ui_runtime.end_workspace_loading(self, defer=defer)

    def _pulse_workspace_loading(self, message: str = "Loading...") -> None:
        ui_runtime.pulse_workspace_loading(self, message)

    def build(self) -> pn.template.FastListTemplate:
        return ui_runtime.build_template(self)
