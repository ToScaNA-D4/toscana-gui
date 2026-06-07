from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from shutil import copy2

import panel as pn

from toscana_gui.numors import run_blocks as numors_run_blocks
from toscana_gui.numors.tasks import (
    NumorsExecutionResult,
    default_numors_state,
    ensure_numors_parfiles_dir,
    list_numors_par_files,
    is_par_file_within_project,
    normalize_numors_state,
    validate_numors_par_file,
)
from toscana_gui.paths import REPO_ROOT
from toscana_gui.persistence import OutputPaths, PARIS_TZ, RunRecord, now_iso

NUMORS_SUBPROCESS_WORKER = REPO_ROOT / "numors_subprocess_worker.py"


class NumorsControllerMixin:
    def _set_numors_source_widget_visibility(self) -> None:
        select_mode = self.numors_source_mode.value == "Select File"
        # PERF: keep both source widgets mounted and toggle visibility instead of rerendering the section.
        self.numors_par_dropdown.visible = select_mode
        self.numors_manual_path_input.visible = not select_mode
        if select_mode:
            self._suspend_numors_events = True
            self._refresh_numors_par_dropdown_options()
            self._suspend_numors_events = False

    def _sync_numors_import_visibility(self) -> None:
        if hasattr(self, "numors_import_card"):
            self.numors_import_card.visible = bool(self.numors_import_prompt.visible)

    def _refresh_numors_par_dropdown_options(self, *, apply_selection: bool = True) -> None:
        if self.current_project_root is None:
            self.numors_par_dropdown.options = {"Open a project first.": ""}
            if apply_selection:
                self.numors_par_dropdown.value = ""
            return

        ensure_numors_parfiles_dir(self.current_project_root)
        do_pars = list_numors_par_files(self.current_project_root)
        if not do_pars:
            self.numors_par_dropdown.options = {"No do_.par files found in processed/parfiles.": ""}
            if apply_selection:
                self.numors_par_dropdown.value = ""
            return

        options = {par_path.name: str(par_path.resolve(strict=False)) for par_path in do_pars}
        self.numors_par_dropdown.options = options

        if not apply_selection:
            current_value = str(getattr(self.numors_par_dropdown, "value", "") or "").strip()
            self.numors_par_dropdown.value = current_value if current_value in options.values() else ""
            return

        state = self._get_numors_state()
        remembered = str(state.get("selected_par_path") or "").strip()
        if remembered and remembered in options.values():
            selected_value = remembered
        else:
            selected_value = next(iter(options.values()))

        self.numors_par_dropdown.value = selected_value
        self.numors_manual_path_input.value = selected_value
        if selected_value and selected_value != remembered:
            self._set_numors_selected_path(selected_value)

    def _get_numors_state(self) -> dict:
        if self.current_project_state is None:
            return default_numors_state()
        normalized = normalize_numors_state(self.current_project_state.numors)
        self.current_project_state.numors = normalized
        return normalized

    def _update_numors_block_select(self, options: dict[str, int], value: int) -> None:
        numors_run_blocks.update_numors_block_select(self, options, value)

    def _on_numors_block_select_change(self, event) -> None:
        numors_run_blocks.on_numors_block_select_change(self, event)

    def _latest_numors_run_blocks(self) -> list[dict] | None:
        return numors_run_blocks.latest_numors_run_blocks(self)

    def _latest_selected_numors_plot_files(self) -> list[str]:
        return numors_run_blocks.latest_selected_numors_plot_files(self)

    def _resolve_numors_block_selection(
        self,
        run_blocks: list[dict],
        numors_state: dict,
    ) -> tuple[int, int, list[str]]:
        return numors_run_blocks.resolve_numors_block_selection(run_blocks, numors_state)

    def _refresh_numors_run_blocks_view(self, latest_record=None) -> None:
        numors_run_blocks.refresh_numors_run_blocks_view(self, latest_record)

    def _on_numors_prev_run_block(self, _event=None) -> None:
        numors_run_blocks.on_numors_prev_run_block(self, _event)

    def _on_numors_next_run_block(self, _event=None) -> None:
        numors_run_blocks.on_numors_next_run_block(self, _event)

    def _on_numors_prev_plot(self, _event=None) -> None:
        numors_run_blocks.on_numors_prev_plot(self, _event)

    def _on_numors_next_plot(self, _event=None) -> None:
        numors_run_blocks.on_numors_next_plot(self, _event)

    def _persist_numors_state(self, state: dict | None = None) -> None:
        if self.current_project_state is None:
            return
        self.current_project_state.numors = normalize_numors_state(
            self._get_numors_state() if state is None else state
        )
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()

    def _load_numors_state_into_widgets(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        state = self._get_numors_state()
        selected_par_path = state.get("selected_par_path", "")

        self._suspend_numors_events = True
        self.numors_source_mode.value = state["source_mode"]
        self.numors_manual_path_input.value = selected_par_path
        self._refresh_numors_par_dropdown_options(
            apply_selection=self.numors_source_mode.value == "Select File"
        )
        self._suspend_numors_events = False
        self._pending_numors_import_path = None
        self.numors_import_prompt.visible = False
        self._set_numors_source_widget_visibility()
        self._sync_numors_import_visibility()

        validation_state = state["validation"]
        self.numors_run_button.disabled = not validation_state.get("is_valid", False)

        if validation_state.get("is_valid"):
            self.numors_message.object = "Selected .par file is ready to run."
            self.numors_message.alert_type = "success"
            self.numors_message.visible = False
            self._show_success_toast("Selected .par file is ready to run")
        elif selected_par_path:
            self.numors_message.object = (
                validation_state.get("error")
                or "The remembered .par selection needs validation."
            )
            self.numors_message.alert_type = "warning"
            self.numors_message.visible = False
            self._show_warning_toast(self.numors_message.object)
        else:
            self.numors_message.object = "Choose a .par file and validate it."
            self.numors_message.alert_type = "secondary"
            self.numors_message.visible = False
            self._show_info_toast(self.numors_message.object)

        self._refresh_numors_run_blocks_view()

    def _set_numors_selected_path(self, path: str) -> None:
        if self.current_project_state is None:
            return
        state = self._get_numors_state()
        state["selected_par_path"] = path
        validation_state = state["validation"]
        validation_state.update(
            {
                "is_valid": False,
                "selected_par_path": path,
                "resolved_rawdata_path": None,
                "resolved_efffile_path": None,
                "resolved_decfile_path": None,
                "file_accessible": False,
                "plot_enabled": False,
                "error": None,
            }
        )
        self.numors_run_button.disabled = True
        self._persist_numors_state(state)
        self._refresh_numors_run_blocks_view()

    def _on_numors_source_mode_change(self, event) -> None:
        if self._suspend_numors_events or self.current_project_state is None or event.new == event.old:
            return
        self._clear_numors_import_prompt()
        state = self._get_numors_state()
        state["source_mode"] = event.new
        self._persist_numors_state(state)
        self.numors_message.object = "Input mode changed. Choose a .par file."
        self.numors_message.alert_type = "secondary"
        self.numors_message.visible = False
        self.numors_run_button.disabled = True
        self._set_numors_source_widget_visibility()
        self._sync_numors_import_visibility()
        self._refresh_interaction_states()

    def _on_numors_par_dropdown_change(self, event) -> None:
        if self._suspend_numors_events or self.current_project_state is None:
            return
        if event.new == event.old:
            return
        selected_path = str(event.new or "").strip()
        self._clear_numors_import_prompt()
        self.numors_manual_path_input.value = selected_path
        self._set_numors_selected_path(selected_path)
        self.numors_message.object = "Selected file changed. Validate it to continue."
        self.numors_message.alert_type = "secondary"
        self.numors_message.visible = False
        self._show_info_toast(self.numors_message.object)
        self._sync_numors_import_visibility()
        self._refresh_interaction_states()

    def _on_numors_manual_path_change(self, event) -> None:
        if self._suspend_numors_events or self.current_project_state is None:
            return
        current_value = event.new.strip()
        state = self._get_numors_state()
        if current_value == state.get("selected_par_path", ""):
            return
        self._clear_numors_import_prompt()
        self._set_numors_selected_path(current_value)
        if current_value:
            self.numors_message.object = "Path changed. Validate it to continue."
            self.numors_message.alert_type = "secondary"
            self.numors_message.visible = False
            self._show_info_toast(self.numors_message.object)
        else:
            self.numors_message.object = "Choose a .par file and validate it."
            self.numors_message.alert_type = "secondary"
        self._sync_numors_import_visibility()
        self._refresh_interaction_states()

    def _validate_numors_selection(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self.current_project_state is None:
            return

        candidate_path = self._get_numors_candidate_path()
        if candidate_path is None:
            self.numors_message.object = "Select a .par file path first."
            self.numors_message.alert_type = "danger"
            self.numors_message.visible = False
            self._show_error_toast(self.numors_message.object)
            # self._render_current_screen()
            return

        self.numors_manual_path_input.value = str(candidate_path)
        self._set_numors_selected_path(str(candidate_path))
        if not is_par_file_within_project(candidate_path, self.current_project_root):
            self._prompt_numors_import(candidate_path)
            # self._render_current_screen()
            return

        self._clear_numors_import_prompt()
        self._apply_numors_validation(candidate_path)
        # self._render_current_screen()

    def _get_numors_candidate_path(self) -> Path | None:
        if self.numors_source_mode.value == "Select File":
            candidate = str(self.numors_par_dropdown.value or "").strip()
            if not candidate:
                return None
            return Path(candidate).expanduser()

        candidate = self.numors_manual_path_input.value.strip()
        if not candidate:
            return None
        return Path(candidate).expanduser()

    def _prompt_numors_import(self, candidate_path: Path) -> None:
        self._pending_numors_import_path = candidate_path.resolve(strict=False)
        self.numors_import_prompt.object = (
            "The selected .par file is outside the current project. "
            "Copy it into `processed/parfiles/` to continue."
        )
        self.numors_import_prompt.alert_type = "warning"
        self.numors_import_prompt.visible = True
        self.numors_message.object = "Copy the selected .par file into the project to validate it."
        self.numors_message.alert_type = "warning"
        self.numors_message.visible = False
        self._show_warning_toast("Copy the selected .par file into the project to validate it.")
        self.numors_run_button.disabled = True
        self._sync_numors_import_visibility()

    def _copy_numors_file_into_project(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.current_project_root is None or self._pending_numors_import_path is None:
            return

        source_path = self._pending_numors_import_path
        target_dir = ensure_numors_parfiles_dir(self.current_project_root)
        target_path = target_dir / source_path.name
        if target_path.exists():
            self.numors_message.object = (
                "A .par file with the same name already exists in `processed/parfiles/`. "
                "Rename the source file manually and try again."
            )
            self.numors_message.alert_type = "danger"
            self.numors_message.visible = False
            self._show_error_toast(self.numors_message.object)
            self.numors_import_prompt.alert_type = "danger"
            self.numors_import_prompt.object = (
                "Import blocked because a file with the same name already exists."
            )
            self.numors_import_prompt.visible = True
            self._sync_numors_import_visibility()
            self._refresh_interaction_states()
            return

        copy2(source_path, target_path)
        self._clear_numors_import_prompt()
        resolved_target = str(target_path.resolve(strict=False))
        self._suspend_numors_events = True
        self._refresh_numors_par_dropdown_options(apply_selection=False)
        self.numors_par_dropdown.value = resolved_target
        self.numors_manual_path_input.value = resolved_target
        self._suspend_numors_events = False
        self._set_numors_selected_path(str(target_path))
        self._apply_numors_validation(target_path)
        self._show_success_toast("Parameter file copied into the project.")
        self._sync_numors_import_visibility()
        self._refresh_interaction_states()

    def _cancel_numors_import(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        self._clear_numors_import_prompt()
        self.numors_message.object = "Import cancelled."
        self.numors_message.alert_type = "secondary"
        self.numors_message.visible = False
        self._sync_numors_import_visibility()
        self._refresh_interaction_states()

    def _clear_numors_import_prompt(self) -> None:
        self._pending_numors_import_path = None
        self.numors_import_prompt.object = ""
        self.numors_import_prompt.visible = False
        self.numors_import_prompt.alert_type = "warning"
        self._sync_numors_import_visibility()

    def _apply_numors_validation(self, par_file: Path) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        validation_result = validate_numors_par_file(par_file, self.current_project_root)
        state = self._get_numors_state()
        state["selected_par_path"] = str(par_file.resolve(strict=False))
        state["validation"] = validation_result.to_state()
        self._persist_numors_state(state)
        self.numors_run_button.disabled = not validation_result.is_valid

        if validation_result.is_valid:
            self.numors_message.object = "Selected .par file is ready to run."
            self.numors_message.alert_type = "success"
            self.numors_message.visible = False
            self._show_success_toast("Selected .par file is ready to run.")
            return

        self.numors_message.object = validation_result.error or "Validation failed."
        self.numors_message.alert_type = "danger"
        self.numors_message.visible = False
        self._show_error_toast(self.numors_message.object)

    def _notify_numors_execution_pending(self, _event=None) -> None:
        if self.operation_in_progress:
            self._show_workspace_blocked_message()
            return
        if self.numors_run_button.disabled:
            return
        self._start_numors_execution()

    def _start_numors_execution(self) -> None:
        if self.current_project_root is None or self.current_project_state is None:
            return

        validation_state = self._get_numors_state()["validation"]
        selected_par_path = validation_state.get("selected_par_path")
        if not validation_state.get("is_valid") or not selected_par_path:
            self.numors_message.object = "Validate a .par file before running d4creg."
            self.numors_message.alert_type = "danger"
            self.numors_message.visible = False
            self._show_error_toast(self.numors_message.object)
            # self._render_current_screen()
            return

        run_id = self._create_run_id()
        stdout_file = self.current_project_root / "processed" / "logfiles" / f"{run_id}-stdout.txt"
        run_record = RunRecord(
            run_id=run_id,
            workflow="numors",
            status="running",
            started_at=now_iso(),
            summary=f"Running `{Path(selected_par_path).name}`",
            workflow_data={"par_file": str(Path(selected_par_path).resolve(strict=False))},
            output_paths=OutputPaths(stdout_file=str(stdout_file)),
        )
        self.current_project_state.runs.append(run_record)
        self.current_project_state.project.updated_at = now_iso()
        self._persist_current_project_state()

        self.operation_in_progress = True
        self._numors_active_run_id = run_id
        self._numors_result_file = (
            self.current_project_root / "processed" / "logfiles" / f"{run_id}-result.json"
        )
        self._clear_workspace_message()
        self.numors_message.object = "Running d4creg. Workspace interactions are blocked until it finishes."
        self.numors_message.alert_type = "warning"
        self.numors_message.visible = False
        self._show_warning_toast(self.numors_message.object)
        self._begin_workspace_loading("Running d4creg...")

        par_file = Path(selected_par_path)
        if self._numors_result_file.exists():
            self._numors_result_file.unlink()

        command = [
            sys.executable,
            str(NUMORS_SUBPROCESS_WORKER),
            str(par_file),
            str(self.current_project_root),
            run_id,
            str(self._numors_result_file),
        ]
        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"

        try:
            self._numors_run_process = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as exc:
            failure = self._build_numors_failure_result(
                run_id,
                stdout_file,
                f"Could not start the d4creg subprocess: {exc}",
            )
            self._numors_run_process = None
            self._finalize_numors_run(failure)
            return

        self._start_numors_run_poll()
        self._refresh_interaction_states()

    def _start_numors_run_poll(self) -> None:
        if self._numors_run_poll is not None:
            self._numors_run_poll.stop()
            self._numors_run_poll = None

        if pn.state.curdoc is not None:
            self._numors_run_poll = pn.state.add_periodic_callback(
                self._finalize_numors_run_if_ready,
                period=500,
                start=True,
            )

    def _finalize_numors_run_if_ready(self) -> None:
        if self._numors_run_process is None or self._numors_run_process.poll() is None:
            return

        if self._numors_run_poll is not None:
            self._numors_run_poll.stop()
            self._numors_run_poll = None

        result = self._load_numors_subprocess_result(self._numors_run_process.returncode)
        self._numors_run_process = None
        self._numors_result_file = None
        self._finalize_numors_run(result)

    def _load_numors_subprocess_result(
        self,
        returncode: int | None,
    ) -> NumorsExecutionResult | None:
        if self._numors_result_file is None:
            return None
        if self._numors_result_file.exists():
            try:
                payload = json.loads(self._numors_result_file.read_text(encoding="utf-8"))
                return NumorsExecutionResult(
                    run_id=str(payload["run_id"]),
                    status=str(payload["status"]),
                    stdout_file=str(payload["stdout_file"]),
                    logfile=payload.get("logfile"),
                    reg_file=payload.get("reg_file"),
                    adat_file=payload.get("adat_file"),
                    qdat_file=payload.get("qdat_file"),
                    run_blocks=list(payload.get("run_blocks", [])),
                    generated_files=list(payload.get("generated_files", [])),
                    plot_files=list(payload.get("plot_files", [])),
                    summary=str(payload.get("summary", "")),
                    error=payload.get("error"),
                )
            except Exception as exc:
                return self._build_numors_failure_result(
                    self._numors_active_run_id or "unknown",
                    self._expected_numors_stdout_file(),
                    f"Could not read the d4creg subprocess result: {exc}",
                )

        return self._build_numors_failure_result(
            self._numors_active_run_id or "unknown",
            self._expected_numors_stdout_file(),
            f"d4creg subprocess exited with code {returncode} without producing a result file.",
        )

    def _expected_numors_stdout_file(self) -> str:
        if self.current_project_root is None or self._numors_active_run_id is None:
            return ""
        return str(
            self.current_project_root
            / "processed"
            / "logfiles"
            / f"{self._numors_active_run_id}-stdout.txt"
        )

    def _build_numors_failure_result(
        self,
        run_id: str,
        stdout_file: str | Path,
        error_message: str,
    ) -> NumorsExecutionResult:
        return NumorsExecutionResult(
            run_id=run_id,
            status="failed",
            stdout_file=str(stdout_file),
            logfile=None,
            reg_file=None,
            adat_file=None,
            qdat_file=None,
            run_blocks=[],
            generated_files=[],
            plot_files=[],
            summary=f"Processed run `{run_id}`, status: `failed`, error: {error_message}",
            error=error_message,
        )

    def _finalize_numors_run(self, result) -> None:
        self.operation_in_progress = False
        try:
            if self.current_project_state is None or self._numors_active_run_id is None:
                self._refresh_interaction_states()
                return

            run_record = next(
                (
                    record
                    for record in reversed(self.current_project_state.runs)
                    if record.run_id == self._numors_active_run_id
                ),
                None,
            )
            if run_record is not None and result is not None:
                run_record.status = result.status
                run_record.finished_at = now_iso()
                run_record.summary = result.summary
                run_record.error = result.error
                run_record.output_paths.stdout_file = result.stdout_file
                run_record.output_paths.logfile = result.logfile
                run_record.output_paths.reg_file = result.reg_file
                run_record.output_paths.adat_file = result.adat_file
                run_record.output_paths.qdat_file = result.qdat_file
                run_record.output_paths.generated_files = list(result.generated_files)
                run_record.workflow_data["run_blocks"] = list(result.run_blocks)
                self.current_project_state.project.updated_at = now_iso()
                self._persist_current_project_state()

            self._numors_active_run_id = None
            if result is None:
                self.numors_message.object = "Numors execution finished without a result payload."
                self.numors_message.alert_type = "danger"
                self.numors_message.visible = False
                self._show_error_toast(self.numors_message.object) 
                self._refresh_interaction_states()
                self._refresh_numors_run_blocks_view()
                return

            if result.status == "succeeded":
                self.numors_message.object = "d4creg finished successfully."
                self.numors_message.alert_type = "success"
                self.numors_message.visible = False
                self._show_success_toast("d4creg finished successfully.")
            else:
                self.numors_message.object = (
                    f"d4creg finished with errors. Partial outputs were preserved. {result.error}"
                )
                self.numors_message.alert_type = "danger"
                self.numors_message.visible = False
                self._show_error_toast(self.numors_message.object)

            state = self._get_numors_state()
            state["selected_run_block_index"] = 0
            state["selected_run_block_plot_index"] = 0
            self._persist_numors_state(state)
            self._refresh_interaction_states()
            self._refresh_numors_run_blocks_view(latest_record=run_record)
        finally:
            self._end_workspace_loading(defer=True)

    def _create_run_id(self) -> str:
        return datetime.now(tz=PARIS_TZ).strftime("%Y%m%d-%H%M%S")
