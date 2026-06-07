from __future__ import annotations

from datetime import datetime
from html import escape
import re
from pathlib import Path

import panel as pn

from toscana_gui.paths import REPO_ROOT
from toscana_gui.persistence import (
    APP_STATE_FILENAME,
    PARIS_TZ,
    PROJECT_STATE_FILENAME,
    RecentProjectEntry,
    create_project_state,
    load_project_state,
    now_iso,
)
from toscana_gui.projects.tasks import (
    WorkspaceTab,
    create_new_project,
    normalize_workspace_tab,
    persist_app_state,
    remember_project,
    restore_project_resume_state,
    save_project_file,
    validate_recent_entry,
)


class ProjectSessionControllerMixin:
    _PROJECT_FOLDER_INVALID_CHARS = r'<>:"/\\|?*'

    def _default_new_project_root(self) -> Path:
        return REPO_ROOT / "Projects"

    def _sanitize_project_name_folder_component(self, project_name: str) -> str:
        tokens: list[str] = []
        for token in project_name.strip().split():
            cleaned = re.sub(
                f"[{re.escape(self._PROJECT_FOLDER_INVALID_CHARS)}]",
                "",
                token,
            )
            cleaned = cleaned.strip().rstrip(" .")
            if cleaned:
                tokens.append(cleaned)
        return "-".join(tokens)

    def _default_project_folder_for_name(self, project_name: str) -> Path:
        root = self._default_new_project_root()
        name = project_name.strip()
        if not name:
            return root
        folder_name = self._sanitize_project_name_folder_component(name)
        if not folder_name:
            return root
        return root / folder_name

    def _set_project_folder_value(self, folder: Path) -> None:
        self._project_folder_autofill_programmatic = True
        try:
            self.project_folder_input.value = str(folder)
        finally:
            self._project_folder_autofill_programmatic = False

    def _reset_project_folder_autofill_for_start(self) -> None:
        placeholder = self.project_folder_input.placeholder.strip()
        current_value = self.project_folder_input.value.strip()
        last_value = getattr(self, "_project_folder_autofill_last_value", None)

        if current_value and current_value not in {placeholder, (last_value or "")}:
            self._project_folder_autofill_enabled = False
            self._project_folder_autofill_last_value = None
            return

        self._project_folder_autofill_enabled = True
        desired = self._default_project_folder_for_name(self.project_name_input.value)
        self._set_project_folder_value(desired)
        self._project_folder_autofill_last_value = str(desired)

    def _maybe_autofill_project_folder_for_name(self, project_name: str) -> None:
        if not getattr(self, "_project_folder_autofill_enabled", False):
            return
        if self.project_folder_mode.value != "Enter folder path":
            return
        last_value = getattr(self, "_project_folder_autofill_last_value", None)
        current_value = self.project_folder_input.value.strip()
        if current_value and last_value and current_value != last_value:
            self._project_folder_autofill_enabled = False
            self._project_folder_autofill_last_value = None
            return

        desired = self._default_project_folder_for_name(project_name)
        self._set_project_folder_value(desired)
        self._project_folder_autofill_last_value = str(desired)

    def _on_project_name_input_change(self, event) -> None:
        if event.new == event.old:
            return
        if self.current_screen != "workspace" or self.workspace_entrypoint != "Start New Project":
            return
        self._maybe_autofill_project_folder_for_name(str(event.new))

    def _on_project_folder_input_change(self, event) -> None:
        if event.new == event.old:
            return
        if getattr(self, "_project_folder_autofill_programmatic", False):
            return
        self._project_folder_autofill_enabled = False
        self._project_folder_autofill_last_value = None

    def _prompt_reset_project(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_file is None or self.current_project_state is None:
            self._show_warning_toast("Open a project before resetting it.")
            return

        processed_dir = self.current_project_root / "processed"
        targets: list[str] = []
        if processed_dir.exists():
            targets.append("`processed/` (everything except `processed/parfiles/`)")
        if not targets:
            targets.append("`processed/` (will be re-created if missing)")

        self.reset_project_prompt.object = (
            "This will permanently delete generated files and reset the project state.\n\n"
            f"**Will delete:** {', '.join(targets)}\n\n"
            "**Will keep:** project name, `rawdata/`, `ntsa-project.json` (reset to blank state), and `processed/parfiles/`.\n\n"
            "Proceed?"
        )
        self.reset_project_prompt.alert_type = "danger"
        self.reset_project_prompt.visible = True
        self._render_current_screen()

    def _cancel_reset_project(self, _event=None) -> None:
        self.reset_project_prompt.visible = False
        self._render_current_screen()

    def _confirm_reset_project(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_file is None or self.current_project_state is None:
            return

        import shutil

        self.operation_in_progress = True
        self._clear_workspace_message()
        self.reset_project_prompt.visible = False
        self._begin_workspace_loading("Resetting project...")
        self._render_current_screen()

        project_root = self.current_project_root.resolve(strict=False)
        processed_dir = project_root / "processed"
        parfiles_dir = processed_dir / "parfiles"

        try:
            if processed_dir.exists() and processed_dir.is_dir():
                for child in processed_dir.iterdir():
                    if child.name.lower() == "parfiles":
                        continue
                    if child.is_dir():
                        shutil.rmtree(child, ignore_errors=False)
                    else:
                        child.unlink(missing_ok=True)

            processed_dir.mkdir(parents=True, exist_ok=True)
            parfiles_dir.mkdir(parents=True, exist_ok=True)

            old_name = self.current_project_state.project.name
            old_created_at = self.current_project_state.project.created_at
            new_state = create_project_state(old_name, last_top_level_tab="project")
            new_state.project.created_at = old_created_at

            self.current_project_state = new_state
            if hasattr(self, "_clear_run_history_viewers"):
                self._clear_run_history_viewers()
            self.current_top_level_tab = "project"
            self.current_project_dirty = False
            self._persist_current_project_state()
            self._load_project_into_editor()
            self._clear_workspace_message()
            self._show_success_toast("Project reset successfully.")
        except Exception as exc:
            self._show_error_toast(f"Project reset failed: {exc}")
        finally:
            self.operation_in_progress = False
            self._render_current_screen()
            self._end_workspace_loading(defer=True)

    def _status_color(self, status: str) -> str:
        if status == "ok":
            return "#2E7D32"
        if status == "missing":
            return "#C62828"
        return "#F9A825"

    def _status_label(self, status: str) -> str:
        if status == "ok":
            return "OK"
        if status == "missing":
            return "Missing"
        return "Invalid"

    def _format_last_opened_at(self, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(PARIS_TZ)
        return parsed.strftime("%d %b %Y %H:%M")

    def _default_project_folder_browser_root(self) -> Path:
        candidate = self.project_folder_input.value.strip()
        if candidate:
            path = Path(candidate).expanduser()
            if path.exists():
                return path if path.is_dir() else path.parent
            if path.parent.exists():
                return path.parent

        placeholder = self.project_folder_input.placeholder.strip()
        if placeholder:
            path = Path(placeholder).expanduser()
            if path.exists():
                return path if path.is_dir() else path.parent
            if path.parent.exists():
                return path.parent

        return REPO_ROOT

    def _default_manual_project_file_browser_root(self) -> Path:
        candidate = self.manual_project_file_input.value.strip()
        if candidate:
            path = Path(candidate).expanduser()
            if path.exists():
                return path.parent if path.is_file() else path
            if path.parent.exists():
                return path.parent

        placeholder = self.manual_project_file_input.placeholder.strip()
        if placeholder:
            path = Path(placeholder).expanduser()
            if path.exists():
                return path.parent if path.is_file() else path
            if path.parent.exists():
                return path.parent

        return REPO_ROOT

    def _update_start_project_message(self) -> None:
        if self.project_folder_mode.value == "Choose folder":
            selected_value = self.project_folder_selected_display.value.strip()
            if selected_value:
                self.start_project_message.object = f"Selected folder: `{selected_value}`"
                self.start_project_message.alert_type = "secondary"
            else:
                self.start_project_message.object = (
                    "Choose a project folder to continue (it must be empty if it exists)."
                )
                self.start_project_message.alert_type = "warning"
        else:
            self.start_project_message.object = "Provide a project name and a target folder."
            self.start_project_message.alert_type = "secondary"

    def _on_project_folder_mode_change(self, event) -> None:
        if event.new == event.old:
            return
        if event.new == "Choose folder":
            self.project_folder_file_selector.directory = str(
                self._default_project_folder_browser_root()
            )
        else:
            self.project_folder_browser_visible = False
        self._update_start_project_message()
        if self.current_screen == "workspace" and self.workspace_entrypoint == "Start New Project":
            self._render_current_screen()

    def _toggle_project_folder_browser(self, _event=None) -> None:
        if self.project_folder_mode.value != "Choose folder":
            return
        self.project_folder_browser_visible = not self.project_folder_browser_visible
        if self.project_folder_browser_visible:
            self.project_folder_file_selector.directory = str(
                self._default_project_folder_browser_root()
            )
        self._render_current_screen()

    def _cancel_project_folder_browser(self, _event=None) -> None:
        self.project_folder_browser_visible = False
        self._render_current_screen()

    def _coerce_to_folder_path(self, path: Path) -> Path:
        if path.exists() and path.is_dir():
            return path
        return path.parent

    def _on_project_folder_candidate_change(self, event) -> None:
        if self.project_folder_mode.value != "Choose folder" or not event.new:
            self._project_folder_candidate = None
            self.project_folder_confirm_button.disabled = True
            return

        selected_raw = event.new[0] if isinstance(event.new, (list, tuple)) else event.new
        try:
            candidate = self._coerce_to_folder_path(Path(str(selected_raw)))
        except (TypeError, ValueError):
            self._project_folder_candidate = None
            self.project_folder_confirm_button.disabled = True
            return

        self._project_folder_candidate = candidate
        self.project_folder_confirm_button.disabled = False

    def _confirm_project_folder_browser(self, _event=None) -> None:
        if self.project_folder_mode.value != "Choose folder" or self._project_folder_candidate is None:
            return

        selected_folder = self._project_folder_candidate.expanduser().resolve()
        self._apply_selected_project_folder(selected_folder)

    def _apply_selected_project_folder(self, selected_folder: Path) -> None:
        self._project_folder_autofill_enabled = False
        self._project_folder_autofill_last_value = None
        self.project_folder_selected_display.value = str(selected_folder)
        self.project_folder_input.value = str(selected_folder)
        self.project_folder_browser_visible = False
        self._project_folder_candidate = None
        self.project_folder_confirm_button.disabled = True
        self._update_start_project_message()
        self._render_current_screen()

    def _choose_project_folder_native(self, _event=None) -> None:
        if self.operation_in_progress or self.project_folder_mode.value != "Choose folder":
            return
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            self.start_project_message.object = f"Native folder picker unavailable: {exc}"
            self.start_project_message.alert_type = "danger"
            self._render_current_screen()
            return

        initialdir = str(self._default_project_folder_browser_root())
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.wm_attributes("-topmost", 1)
            except Exception:
                pass
            folder = filedialog.askdirectory(
                initialdir=initialdir,
                title="Select project folder",
            )
        except Exception as exc:
            self.start_project_message.object = f"Folder picker failed: {exc}"
            self.start_project_message.alert_type = "danger"
            self._render_current_screen()
            return
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass

        if not folder:
            return

        try:
            selected_folder = Path(folder).expanduser().resolve()
        except (TypeError, ValueError) as exc:
            self.start_project_message.object = f"Selected folder is invalid: {exc}"
            self.start_project_message.alert_type = "danger"
            self._render_current_screen()
            return

        self._apply_selected_project_folder(selected_folder)

    def _on_manual_project_file_mode_change(self, event) -> None:
        if event.new == event.old:
            return
        if event.new == "Choose file":
            self.manual_project_file_selector.directory = str(
                self._default_manual_project_file_browser_root()
            )
        else:
            self.manual_project_file_browser_visible = False
            self._manual_project_file_candidate = None
            self.manual_project_file_confirm_button.disabled = True
        if (
            self.current_screen == "workspace"
            and self.workspace_entrypoint == "Continue Previous Project"
        ):
            self._render_current_screen()

    def _on_manual_project_file_input_change(self, event) -> None:
        if event.new == event.old:
            return
        if (
            self.current_screen == "workspace"
            and self.workspace_entrypoint == "Continue Previous Project"
        ):
            # PERF: typing a manual path should only refresh local control state, not rerender the workspace.
            self._refresh_interaction_states()

    def _toggle_manual_project_file_browser(self, _event=None) -> None:
        if self.manual_project_file_mode.value != "Choose file":
            return
        self.manual_project_file_browser_visible = not self.manual_project_file_browser_visible
        if self.manual_project_file_browser_visible:
            self.manual_project_file_selector.directory = str(
                self._default_manual_project_file_browser_root()
            )
        self._render_current_screen()

    def _cancel_manual_project_file_browser(self, _event=None) -> None:
        self.manual_project_file_browser_visible = False
        self._render_current_screen()

    def _on_manual_project_file_candidate_change(self, event) -> None:
        if self.manual_project_file_mode.value != "Choose file" or not event.new:
            self._manual_project_file_candidate = None
            self.manual_project_file_confirm_button.disabled = True
            return

        selected_raw = event.new[0] if isinstance(event.new, (list, tuple)) else event.new
        try:
            candidate = Path(str(selected_raw)).expanduser()
        except (TypeError, ValueError):
            self._manual_project_file_candidate = None
            self.manual_project_file_confirm_button.disabled = True
            return

        self._manual_project_file_candidate = candidate
        self.manual_project_file_confirm_button.disabled = False

    def _confirm_manual_project_file_browser(self, _event=None) -> None:
        if (
            self.manual_project_file_mode.value != "Choose file"
            or self._manual_project_file_candidate is None
        ):
            return
        selected_file = self._manual_project_file_candidate.expanduser().resolve()
        self.manual_project_file_selected_display.value = str(selected_file)
        self.manual_project_file_input.value = str(selected_file)
        self.manual_project_file_browser_visible = False
        self._manual_project_file_candidate = None
        self.manual_project_file_confirm_button.disabled = True
        self._render_current_screen()

    def _choose_manual_project_file_native(self, _event=None) -> None:
        if self.operation_in_progress or self.manual_project_file_mode.value != "Choose file":
            return
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:
            self.continue_project_message.object = f"Native file picker unavailable: {exc}"
            self.continue_project_message.alert_type = "danger"
            self._render_current_screen()
            return

        initialdir = str(self._default_manual_project_file_browser_root())
        root = None
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.wm_attributes("-topmost", 1)
            except Exception:
                pass
            filename = filedialog.askopenfilename(
                initialdir=initialdir,
                title="Select project file",
                filetypes=[
                    ("ToScaNA project file", PROJECT_STATE_FILENAME),
                    ("JSON files", "*.json"),
                    ("All files", "*.*"),
                ],
            )
        except Exception as exc:
            self.continue_project_message.object = f"File picker failed: {exc}"
            self.continue_project_message.alert_type = "danger"
            self._render_current_screen()
            return
        finally:
            if root is not None:
                try:
                    root.destroy()
                except Exception:
                    pass

        if not filename:
            return

        try:
            selected_file = Path(filename).expanduser().resolve()
        except (TypeError, ValueError) as exc:
            self.continue_project_message.object = f"Selected file is invalid: {exc}"
            self.continue_project_message.alert_type = "danger"
            self._render_current_screen()
            return

        self.manual_project_file_selected_display.value = str(selected_file)
        self.manual_project_file_input.value = str(selected_file)
        self.manual_project_file_browser_visible = False
        self._manual_project_file_candidate = None
        self.manual_project_file_confirm_button.disabled = True
        self._render_current_screen()

    def _persist_app_state(self) -> None:
        persist_app_state(REPO_ROOT / APP_STATE_FILENAME, self.app_state)

    def _remember_current_project(self) -> None:
        if self.current_project_state is None or self.current_project_file is None:
            return
        remember_project(
            self.app_state,
            self.current_project_state,
            self.current_project_file,
        )
        self._persist_app_state()

    def _persist_current_project_state(self) -> None:
        if self.current_project_state is None or self.current_project_file is None:
            return
        save_project_file(self.current_project_file, self.current_project_state)

    def _load_project_into_editor(self) -> None:
        if self.current_project_state is None:
            return
        self._suspend_dirty_tracking = True
        self.project_editor_name_input.value = self.current_project_state.project.name
        self._suspend_dirty_tracking = False
        self.current_project_dirty = False
        self.project_editor_message.object = "No unsaved changes."
        self.project_editor_message.alert_type = "secondary"
        self._load_numors_state_into_widgets()
        if hasattr(self, "_load_background_state_into_widgets"):
            self._load_background_state_into_widgets()
        if hasattr(self, "_load_normalization_state_into_widgets"):
            self._load_normalization_state_into_widgets()
        if hasattr(self, "_load_self_scattering_state_into_widgets"):
            self._load_self_scattering_state_into_widgets()
        if hasattr(self, "_load_ft_state_into_widgets"):
            self._load_ft_state_into_widgets()

    def _restore_project_session(self) -> None:
        if self.current_project_state is None:
            return
        self.current_top_level_tab, updated = restore_project_resume_state(
            self.current_project_state
        )
        if updated:
            self._persist_current_project_state()

    def _open_project(self, project_file: Path) -> None:
        if hasattr(self, "_reset_toast_once"):
            self._reset_toast_once()
        if hasattr(self, "_reset_normalization_runtime_state"):
            self._reset_normalization_runtime_state()
        if hasattr(self, "_reset_self_scattering_runtime_state"):
            self._reset_self_scattering_runtime_state()
        if hasattr(self, "_reset_ft_runtime_state"):
            self._reset_ft_runtime_state()
        project_state = load_project_state(project_file)
        self.current_project_state = project_state
        if hasattr(self, "_clear_run_history_viewers"):
            self._clear_run_history_viewers()
        self.current_project_file = project_file.resolve()
        self.current_project_root = self.current_project_file.parent
        self.workspace_result = "opened"
        self._restore_project_session()
        self._load_project_into_editor()
        self._remember_current_project()
        self._clear_workspace_message()
        self._pulse_workspace_loading("Opening project...")
        self._render_current_screen()
        if (
            self.current_project_state.resume.has_static_plot_warning
            and self.current_project_state.resume.static_plot_warning
        ):
            self._show_warning_toast(self.current_project_state.resume.static_plot_warning)
        self._show_success_toast(
            f"Project {self.current_project_state.project.name} opened successfully."
        )

    def _remove_recent_project(self, project_file: str) -> None:
        self.app_state.remove_project(project_file)
        self._persist_app_state()
        if self._selected_recent_project_file == project_file:
            self._selected_recent_project_file = None
        self._refresh_recent_projects_view()
        self._render_current_screen()

    def _refresh_recent_projects_view(self) -> None:
        validated_entries: list[RecentProjectEntry] = [
            validate_recent_entry(entry)
            for entry in self.app_state.recent_projects
        ]
        self.app_state.recent_projects = validated_entries
        self._persist_app_state()

        if not validated_entries:
            self.recent_projects_column[:] = [
                pn.pane.Markdown("No recent projects yet.", sizing_mode="stretch_width")
            ]
            return

        project_files = {entry.project_file for entry in validated_entries}
        if self._selected_recent_project_file not in project_files:
            self._selected_recent_project_file = validated_entries[0].project_file

        selected_entry = next(
            (
                entry
                for entry in validated_entries
                if entry.project_file == self._selected_recent_project_file
            ),
            validated_entries[0],
        )

        list_rows: list[object] = []
        for entry in validated_entries:
            dot_color = self._status_color(entry.status)
            selected = entry.project_file == self._selected_recent_project_file
            select_button = pn.widgets.Button(
                name=entry.project_name,
                button_type="primary" if selected else "light",
                sizing_mode="stretch_width",
                styles={
                    "text-align": "left",
                    "white-space": "nowrap",
                    "overflow": "hidden",
                    "text-overflow": "ellipsis",
                },
            )

            def _make_select_handler(project_file: str) -> callable:
                def _handler(_event=None) -> None:
                    self._selected_recent_project_file = project_file
                    self.manual_project_file_input.value = ""
                    self.manual_project_file_selected_display.value = ""
                    self._manual_project_file_candidate = None
                    self.manual_project_file_browser_visible = False
                    self._render_current_screen()

                return _handler

            select_button.on_click(_make_select_handler(entry.project_file))
            list_rows.append(
                pn.Row(
                    pn.pane.HTML(
                        f"""
                        <div style="
                          width: 10px;
                          height: 10px;
                          border-radius: 50%;
                          background: {dot_color};
                          margin-top: 8px;
                        "></div>
                        """,
                        width=16,
                        sizing_mode="fixed",
                    ),
                    select_button,
                    sizing_mode="stretch_width",
                    styles={
                        "padding": "4px 6px",
                        "border-radius": "10px",
                        "border": "1px solid rgba(0,0,0,0.06)" if not selected else "1px solid rgba(11,111,164,0.45)",
                        "background": "rgba(11,111,164,0.06)" if selected else "transparent",
                    },
                )
            )

        list_pane = pn.Column(
            *list_rows,
            sizing_mode="stretch_width",
            scroll=True,
            max_height=360,
            styles={
                "flex": "1 1 260px",
                "min-width": "260px",
            },
        )

        status_color = self._status_color(selected_entry.status)
        status_label = self._status_label(selected_entry.status)
        if selected_entry.status == "ok":
            status_bg = "rgba(46, 125, 50, 0.12)"
        elif selected_entry.status == "missing":
            status_bg = "rgba(198, 40, 40, 0.12)"
        else:
            status_bg = "rgba(249, 168, 37, 0.16)"
        status_pill = pn.pane.HTML(
            f"""
            <div style="
              display: inline-block;
              padding: 4px 10px;
              border-radius: 999px;
              font-weight: 600;
              font-size: 0.9rem;
              color: {status_color};
              background: {status_bg};
              border: 1px solid rgba(0,0,0,0.10);
            ">
              {status_label}
            </div>
            """,
            sizing_mode="stretch_width",
        )

        open_button = pn.widgets.Button(
            name="Open",
            button_type="primary",
            width=120,
            disabled=selected_entry.status != "ok",
        )
        remove_button = pn.widgets.Button(
            name="Remove",
            button_type="light",
            width=120,
        )

        def _open_selected(_event=None, project_file: str = selected_entry.project_file) -> None:
            self._open_project(Path(project_file))

        def _remove_selected(_event=None, project_file: str = selected_entry.project_file) -> None:
            self._remove_recent_project(project_file)

        open_button.on_click(_open_selected)
        remove_button.on_click(_remove_selected)

        warning_block = (
            pn.pane.Alert(
                selected_entry.warning,
                alert_type="warning" if selected_entry.status != "missing" else "danger",
                sizing_mode="stretch_width",
            )
            if selected_entry.warning
            else pn.Spacer(height=0)
        )

        details_pane = pn.Column(
            status_pill,
            pn.pane.HTML(
                f"""
                <div style="line-height: 1.6;">
                  <div><strong>Project:</strong> {escape(selected_entry.project_name)}</div>
                  <div><strong>Path:</strong> <code style="overflow-wrap: anywhere;">{escape(selected_entry.project_file)}</code></div>
                  <div><strong>Last opened:</strong> {escape(self._format_last_opened_at(selected_entry.last_opened_at))}</div>
                </div>
                """,
                sizing_mode="stretch_width",
            ),
            warning_block,
            pn.Row(open_button, remove_button),
            sizing_mode="stretch_width",
            styles={
                "flex": "2 1 360px",
                "min-width": "320px",
            },
        )

        self.recent_projects_column[:] = [
            pn.FlexBox(
                list_pane,
                details_pane,
                gap="18px",
                flex_wrap="wrap",
                sizing_mode="stretch_width",
                styles={"align-items": "flex-start"},
            )
        ]

    def _on_project_editor_name_change(self, _event) -> None:
        if self._suspend_dirty_tracking or self.current_project_state is None:
            return
        saved_name = self.current_project_state.project.name
        current_name = self.project_editor_name_input.value.strip()
        self.current_project_dirty = current_name != saved_name
        if self.current_project_dirty:
            self.project_editor_message.object = "Unsaved changes detected."
            self.project_editor_message.alert_type = "warning"
        else:
            self.project_editor_message.object = "No unsaved changes."
            self.project_editor_message.alert_type = "secondary"

    def _request_navigation(self, action: str) -> None:
        if self.operation_in_progress:
            self.pending_navigation_action = None
            return

        if self.current_project_state is not None and self.current_project_dirty:
            self.pending_navigation_action = action
            self._render_current_screen()
            return

        self.pending_navigation_action = None
        self._perform_navigation(action)

    def _perform_navigation(self, action: str) -> None:
        if hasattr(self, "_reset_toast_once"):
            self._reset_toast_once()
        self._clear_workspace_message()
        if action == "start":
            self.workspace_entrypoint = "Start New Project"
            self.workspace_result = None
            self.current_project_state = None
            self.current_project_root = None
            self.current_project_file = None
            self.current_project_dirty = False
            self.current_top_level_tab = "project"
            self._reset_project_folder_autofill_for_start()
            self._update_start_project_message()
        elif action == "continue":
            self.workspace_entrypoint = "Continue Previous Project"
            self.workspace_result = None
            self.continue_project_message.object = (
                "Choose a recent project or open an `ntsa-project.json` file manually."
            )
            self.continue_project_message.alert_type = "secondary"
        self.current_screen = "workspace"
        self._pulse_workspace_loading("Opening workspace...")
        self._render_current_screen()

    def _go_to_workspace_from_start(self, _event) -> None:
        self._request_navigation("start")

    def _go_to_workspace_from_continue(self, _event) -> None:
        self._request_navigation("continue")

    def _go_to_landing_page(self, _event) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        self.current_screen = "landing"
        self._render_current_screen()

    def _save_current_project(self, _event=None) -> bool:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return False
        if self.current_project_state is None or self.current_project_file is None:
            return False
        updated_name = self.project_editor_name_input.value.strip()
        if not updated_name:
            self.project_editor_message.object = "Project name cannot be empty."
            self.project_editor_message.alert_type = "danger"
            return False

        self.current_project_state.project.name = updated_name
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()
        self.current_project_dirty = False
        self._remember_current_project()
        self._load_project_into_editor()
        self._render_current_screen()
        self._show_success_toast("Project saved successfully.")
        return True

    def _discard_current_project_changes(self) -> None:
        if self.current_project_state is None:
            return
        self._load_project_into_editor()

    def _save_and_continue(self, _event) -> None:
        if self.pending_navigation_action is None:
            return
        if self._save_current_project():
            action = self.pending_navigation_action
            self.pending_navigation_action = None
            self._perform_navigation(action)

    def _discard_and_continue(self, _event) -> None:
        if self.pending_navigation_action is None:
            return
        action = self.pending_navigation_action
        self.pending_navigation_action = None
        self._discard_current_project_changes()
        self.current_project_dirty = False
        self.project_editor_message.object = "Unsaved changes were discarded."
        self.project_editor_message.alert_type = "secondary"
        self._perform_navigation(action)

    def _cancel_pending_navigation(self, _event) -> None:
        self.pending_navigation_action = None
        self._render_current_screen()

    def _set_top_level_tab(self, tab_name: str, *, persist: bool) -> None:
        normalized_tab = normalize_workspace_tab(tab_name)
        self.current_top_level_tab = normalized_tab
        if self.current_project_state is None:
            return

        if self.current_project_state.resume.last_top_level_tab != normalized_tab:
            self.current_project_state.resume.last_top_level_tab = normalized_tab
            self.current_project_state.project.updated_at = now_iso()
            if persist:
                self._persist_current_project_state()

    def _create_project(self, _event) -> None:
        project_name = self.project_name_input.value.strip()
        project_folder_raw = self.project_folder_input.value.strip()

        if not project_name:
            self.start_project_message.object = "Project name is required."
            self.start_project_message.alert_type = "danger"
            return
        if not project_folder_raw:
            self.start_project_message.object = "Project folder is required."
            self.start_project_message.alert_type = "danger"
            return

        project_root = Path(project_folder_raw).expanduser()
        if project_root.exists():
            if not project_root.is_dir():
                self.start_project_message.object = (
                    "Project folder path exists but is not a directory."
                )
                self.start_project_message.alert_type = "danger"
                return
            if any(project_root.iterdir()):
                self.start_project_message.object = (
                    "Project folder must be empty before creating a new project."
                )
                self.start_project_message.alert_type = "danger"
                return
        else:
            try:
                project_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                self.start_project_message.object = (
                    f"Could not create the project folder: {exc}. "
                    "Choose another folder or check permissions."
                )
                self.start_project_message.alert_type = "danger"
                return

        try:
            project_state, project_file = create_new_project(project_name, project_root)
        except OSError as exc:
            self.start_project_message.object = (
                f"Could not write project files to the selected folder: {exc}. "
                "Choose another folder or check permissions."
            )
            self.start_project_message.alert_type = "danger"
            return
        if hasattr(self, "_reset_normalization_runtime_state"):
            self._reset_normalization_runtime_state()
        if hasattr(self, "_reset_self_scattering_runtime_state"):
            self._reset_self_scattering_runtime_state()
        self.current_project_root = project_root.resolve()
        self.current_project_file = project_file
        self.current_project_state = project_state
        if hasattr(self, "_clear_run_history_viewers"):
            self._clear_run_history_viewers()
        self.workspace_result = "created"
        self.current_top_level_tab = "project"
        self._load_project_into_editor()
        self._remember_current_project()
        self._clear_workspace_message()
        self._pulse_workspace_loading("Creating project...")
        self._render_current_screen()
        self._show_success_toast(f"Project {project_name} created successfully.")

    def _open_project_from_manual_path(self, _event) -> None:
        project_file_raw = self.manual_project_file_input.value.strip()
        if not project_file_raw:
            self.continue_project_message.object = "Project file path is required."
            self.continue_project_message.alert_type = "danger"
            return

        project_file = Path(project_file_raw).expanduser()
        if not project_file.exists():
            self.continue_project_message.object = "Project file was not found."
            self.continue_project_message.alert_type = "danger"
            return

        if not project_file.is_file() or project_file.name != PROJECT_STATE_FILENAME:
            self.continue_project_message.object = (
                f"Select a `{PROJECT_STATE_FILENAME}` file."
            )
            self.continue_project_message.alert_type = "danger"
            return

        try:
            self._open_project(project_file)
        except Exception as exc:
            self.continue_project_message.object = f"Could not open project: {exc}"
            self.continue_project_message.alert_type = "danger"
            return

    def _make_workspace_navigation_handler(self, tab_name: WorkspaceTab):
        def _handler(_event) -> None:
            self._navigate_to_workspace_section(tab_name)

        return _handler

    def _navigate_to_workspace_section(self, tab_name: WorkspaceTab) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        # Defensive: ensure no stale loading overlay blocks navigation (loading should never
        # outlive an operation, but UI exceptions can occasionally leave it stuck).
        if hasattr(self, "_end_workspace_loading"):
            try:
                for _ in range(5):
                    self._end_workspace_loading(defer=False)
            except Exception:
                pass
        self._clear_workspace_message()
        self._set_top_level_tab(tab_name, persist=True)
        self._pulse_workspace_loading(f"Opening {tab_name.title()}...")
        self._render_current_screen()
