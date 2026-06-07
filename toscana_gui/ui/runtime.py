from __future__ import annotations

import math
from pathlib import Path

import panel as pn

from toscana_gui.background.tasks import background_sample_key
from toscana_gui.ui.screens import build_landing_page
from toscana_gui.ui.screens.workspace import build_workspace_page_body
from toscana_gui.ui.notifications import ToastLevel


def render_current_screen(shell) -> None:
    shell._refresh_workspace_button_states()
    shell._refresh_interaction_states()
    if shell.current_screen == "landing":
        shell._active_root_screen = "landing"
        shell.content[:] = [build_landing_page(shell)]
    else:
        # PERF: keep the workspace shell mounted and refresh only its body.
        workspace_page = _ensure_workspace_page(shell)
        _refresh_workspace_page(shell)
        if not shell.content.objects or shell.content.objects[0] is not workspace_page:
            shell.content[:] = [workspace_page]
        shell._active_root_screen = "workspace"


def _ensure_workspace_page(shell):
    workspace_page = getattr(shell, "_workspace_page", None)
    if workspace_page is not None:
        return workspace_page

    # PERF: persistent header/body panes avoid tearing down the whole workspace page.
    shell._workspace_title_pane = pn.pane.Markdown(
        "# Workspace",
        sizing_mode="stretch_width",
    )
    shell._workspace_entrypoint_pane = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
    )
    shell._workspace_loading_message = pn.pane.Alert(
        "",
        alert_type="secondary",
        visible=False,
        sizing_mode="stretch_width",
    )
    shell._workspace_body = pn.Column(sizing_mode="stretch_both")
    shell._workspace_page = pn.Column(
        shell._workspace_title_pane,
        shell._workspace_entrypoint_pane,
        shell._workspace_loading_message,
        shell._workspace_body,
        sizing_mode="stretch_both",
    )
    _apply_workspace_loading_state(shell)
    return shell._workspace_page


def _refresh_workspace_page(shell) -> None:
    # PERF: update the existing panes in place instead of replacing the root page.
    shell._workspace_title_pane.object = "# Workspace"
    shell._workspace_entrypoint_pane.object = f"**Entered from:** {shell.workspace_entrypoint}"
    shell._workspace_body[:] = build_workspace_page_body(shell)


def begin_workspace_loading(shell, message: str = "Loading...") -> None:
    shell._workspace_loading_depth = int(getattr(shell, "_workspace_loading_depth", 0)) + 1
    shell._workspace_loading_message_text = str(message or "").strip()
    _apply_workspace_loading_state(shell)


def end_workspace_loading(shell, *, defer: bool = False) -> None:
    if defer and pn.state.curdoc is not None:
        pn.state.curdoc.add_next_tick_callback(lambda: _end_workspace_loading_now(shell))
        return
    _end_workspace_loading_now(shell)


def pulse_workspace_loading(shell, message: str = "Loading...") -> None:
    begin_workspace_loading(shell, message=message)
    end_workspace_loading(shell, defer=True)


def _end_workspace_loading_now(shell) -> None:
    depth = int(getattr(shell, "_workspace_loading_depth", 0))
    if depth <= 0:
        return
    shell._workspace_loading_depth = depth - 1
    if shell._workspace_loading_depth == 0:
        shell._workspace_loading_message_text = ""
    _apply_workspace_loading_state(shell)


def _apply_workspace_loading_state(shell) -> None:
    is_loading = int(getattr(shell, "_workspace_loading_depth", 0)) > 0
    loading_message = str(getattr(shell, "_workspace_loading_message_text", "") or "").strip()
    shell.content.loading = is_loading

    loading_pane = getattr(shell, "_workspace_loading_message", None)
    if loading_pane is None:
        return

    loading_pane.object = loading_message if is_loading else ""
    loading_pane.visible = is_loading and bool(loading_message)


def refresh_interaction_states(shell) -> None:
    disabled = shell.operation_in_progress
    shell.reset_project_button.disabled = disabled or shell.current_project_state is None
    shell.reset_project_confirm_button.disabled = disabled
    shell.reset_project_cancel_button.disabled = disabled
    shell.project_editor_name_input.disabled = disabled
    shell.save_project_button.disabled = disabled
    shell.numors_source_mode.disabled = disabled
    numors_picker_mode = shell.numors_source_mode.value == "Select File"
    shell.numors_par_dropdown.disabled = disabled or not numors_picker_mode
    shell.numors_manual_path_input.disabled = disabled or numors_picker_mode
    shell.numors_validate_button.disabled = disabled
    shell.numors_block_select.disabled = disabled
    shell.numors_import_confirm_button.disabled = disabled
    shell.numors_import_cancel_button.disabled = disabled
    shell.background_source_mode.disabled = disabled
    background_picker_mode = shell.background_source_mode.value == "Select File"
    shell.background_par_dropdown.disabled = disabled or not background_picker_mode
    shell.background_manual_path_input.disabled = disabled or background_picker_mode
    shell.background_validate_button.disabled = disabled
    shell.background_extract_button.disabled = disabled or not shell._get_background_state()[
        "validation"
    ].get("is_valid", False)
    shell.background_subtraction_method.disabled = disabled
    if hasattr(shell, "background_sample_method_select"):
        shell.background_sample_method_select.disabled = disabled
    if hasattr(shell, "background_vanadium_method_select"):
        shell.background_vanadium_method_select.disabled = disabled
    use_custom_draft = bool(getattr(getattr(shell, "background_sample_use_custom_t_toggle", None), "value", False))
    if hasattr(shell, "background_sample_view_switch"):
        shell.background_sample_view_switch.disabled = disabled
    if hasattr(shell, "background_sample_use_custom_t_toggle"):
        shell.background_sample_use_custom_t_toggle.disabled = disabled
    if hasattr(shell, "background_sample_custom_t_input"):
        shell.background_sample_custom_t_input.disabled = disabled or not use_custom_draft

    best_t_ok = False
    try:
        state = shell._get_background_state() if hasattr(shell, "_get_background_state") else {}
        par_path_str = (
            str(getattr(shell, "_background_cached_par_path", "") or "").strip()
            or str(state.get("validation", {}).get("selected_par_path") or "").strip()
        )
        project_root = getattr(shell, "current_project_root", None)
        sample_key = (
            background_sample_key(Path(par_path_str), project_root)
            if par_path_str and project_root is not None
            else None
        )
        cached = state.get("measurements_by_par") if isinstance(state, dict) else None
        entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
        linear = entry.get("linear_combination") if isinstance(entry, dict) else None
        best_t = linear.get("best_t") if isinstance(linear, dict) else None
        if isinstance(best_t, (int, float)) and math.isfinite(float(best_t)):
            best_t_ok = True
    except Exception:
        best_t_ok = False

    custom_t_ok = False
    if hasattr(shell, "background_sample_custom_t_input") and use_custom_draft:
        custom_val = getattr(shell.background_sample_custom_t_input, "value", None)
        if isinstance(custom_val, (int, float)) and math.isfinite(float(custom_val)):
            custom_t_ok = True

    if hasattr(shell, "background_sample_use_computed_t_button"):
        shell.background_sample_use_computed_t_button.disabled = disabled or not best_t_ok
    if hasattr(shell, "background_sample_use_custom_t_button"):
        shell.background_sample_use_custom_t_button.disabled = disabled or not custom_t_ok

    shell.background_linear_t_start.disabled = disabled or use_custom_draft
    shell.background_linear_t_stop.disabled = disabled or use_custom_draft
    shell.background_linear_t_step.disabled = disabled or use_custom_draft
    shell.background_linear_smoothing.disabled = disabled or use_custom_draft
    shell.background_linear_ignore_points.disabled = disabled or use_custom_draft
    shell.background_linear_compute_button.disabled = disabled or use_custom_draft
    shell.background_linear_t_mode.disabled = disabled
    shell.background_linear_custom_t.disabled = disabled or shell.background_linear_t_mode.value != "Use custom t"

    van_use_custom_draft = bool(getattr(getattr(shell, "background_vanadium_use_custom_t_toggle", None), "value", False))
    if hasattr(shell, "background_vanadium_view_switch"):
        shell.background_vanadium_view_switch.disabled = disabled
    if hasattr(shell, "background_vanadium_use_custom_t_toggle"):
        shell.background_vanadium_use_custom_t_toggle.disabled = disabled
    if hasattr(shell, "background_vanadium_custom_t_input"):
        shell.background_vanadium_custom_t_input.disabled = disabled or not van_use_custom_draft

    van_best_t_ok = False
    try:
        state = shell._get_background_state() if hasattr(shell, "_get_background_state") else {}
        par_path_str = (
            str(getattr(shell, "_background_cached_par_path", "") or "").strip()
            or str(state.get("validation", {}).get("selected_par_path") or "").strip()
        )
        project_root = getattr(shell, "current_project_root", None)
        sample_key = (
            background_sample_key(Path(par_path_str), project_root)
            if par_path_str and project_root is not None
            else None
        )
        cached = state.get("measurements_by_par") if isinstance(state, dict) else None
        entry = cached.get(sample_key) if sample_key and isinstance(cached, dict) else None
        vanadium = entry.get("vanadium_linear_combination") if isinstance(entry, dict) else None
        best_t = vanadium.get("best_t") if isinstance(vanadium, dict) else None
        if isinstance(best_t, (int, float)) and math.isfinite(float(best_t)):
            van_best_t_ok = True
    except Exception:
        van_best_t_ok = False

    van_custom_t_ok = False
    if hasattr(shell, "background_vanadium_custom_t_input") and van_use_custom_draft:
        custom_val = getattr(shell.background_vanadium_custom_t_input, "value", None)
        if isinstance(custom_val, (int, float)) and math.isfinite(float(custom_val)):
            van_custom_t_ok = True

    if hasattr(shell, "background_vanadium_use_computed_t_button"):
        shell.background_vanadium_use_computed_t_button.disabled = disabled or not van_best_t_ok
    if hasattr(shell, "background_vanadium_use_custom_t_button"):
        shell.background_vanadium_use_custom_t_button.disabled = disabled or not van_custom_t_ok

    if hasattr(shell, "background_vanadium_t_start"):
        shell.background_vanadium_t_start.disabled = disabled or van_use_custom_draft
    if hasattr(shell, "background_vanadium_t_stop"):
        shell.background_vanadium_t_stop.disabled = disabled or van_use_custom_draft
    if hasattr(shell, "background_vanadium_t_step"):
        shell.background_vanadium_t_step.disabled = disabled or van_use_custom_draft
    if hasattr(shell, "background_vanadium_smoothing"):
        shell.background_vanadium_smoothing.disabled = disabled or van_use_custom_draft
    if hasattr(shell, "background_vanadium_ignore_points"):
        shell.background_vanadium_ignore_points.disabled = disabled or van_use_custom_draft
    if hasattr(shell, "background_vanadium_compute_button"):
        shell.background_vanadium_compute_button.disabled = disabled or van_use_custom_draft

    if hasattr(shell, "background_vanadium_t_mode"):
        shell.background_vanadium_t_mode.disabled = disabled
    if hasattr(shell, "background_vanadium_custom_t"):
        shell.background_vanadium_custom_t.disabled = disabled or shell.background_vanadium_t_mode.value != "Use custom t"
    shell.background_import_confirm_button.disabled = disabled
    shell.background_import_cancel_button.disabled = disabled
    shell.background_export_folder_input.disabled = disabled

    ## logic change for background tab 

    is_background_tab = getattr(shell, "current_top_level_tab", None) == "background"

    if hasattr(shell, "background_export_button"):
        if is_background_tab and hasattr(shell, "_background_export_is_ready"):
            export_ready = shell._background_export_is_ready()
        else:
            export_ready = False
        shell.background_export_button.disabled = disabled or not export_ready

    shell.background_export_cancel_button.disabled = disabled
    shell.manual_project_file_mode.disabled = disabled
    manual_picker_mode = shell.manual_project_file_mode.value == "Choose file"
    shell.manual_project_file_input.disabled = disabled or manual_picker_mode
    shell.manual_project_file_browse_button.disabled = disabled or not manual_picker_mode
    shell.manual_project_file_native_browse_button.disabled = disabled or not manual_picker_mode
    shell.manual_project_file_confirm_button.disabled = (
        disabled or not manual_picker_mode or shell._manual_project_file_candidate is None
    )
    shell.manual_project_file_cancel_button.disabled = disabled or not manual_picker_mode
    shell.manual_project_file_selector.disabled = disabled or not manual_picker_mode
    shell.manual_open_button.disabled = disabled or not shell.manual_project_file_input.value.strip()
    shell.project_folder_mode.disabled = disabled
    folder_is_picker_mode = shell.project_folder_mode.value == "Choose folder"
    selected_folder_value = shell.project_folder_selected_display.value.strip()
    shell.project_folder_browse_button.disabled = disabled or not folder_is_picker_mode
    shell.project_folder_native_browse_button.disabled = disabled or not folder_is_picker_mode
    shell.project_folder_confirm_button.disabled = (
        disabled or not folder_is_picker_mode or shell._project_folder_candidate is None
    )
    shell.project_folder_cancel_button.disabled = disabled or not folder_is_picker_mode
    shell.project_folder_file_selector.disabled = disabled or not folder_is_picker_mode
    shell.create_project_confirm_button.disabled = (
        disabled or (folder_is_picker_mode and not selected_folder_value)
    )
    shell.project_name_input.disabled = disabled
    shell.project_folder_input.disabled = disabled or folder_is_picker_mode
    shell.numors_run_button.disabled = disabled or not shell._get_numors_state()["validation"].get(
        "is_valid",
        False,
    )
    shell.numors_prev_block_button.disabled = disabled
    shell.numors_next_block_button.disabled = disabled
    shell.numors_prev_plot_button.disabled = disabled
    shell.numors_next_plot_button.disabled = disabled
    if hasattr(shell, "normalization_source_mode"):
        shell.normalization_source_mode.disabled = disabled
        norm_picker_mode = shell.normalization_source_mode.value == "Select File"
        shell.normalization_sample_qdat_dropdown.disabled = disabled or not norm_picker_mode
        shell.normalization_vanadium_qdat_dropdown.disabled = disabled or not norm_picker_mode
        shell.normalization_sample_qdat_path_input.disabled = disabled or norm_picker_mode
        shell.normalization_vanadium_qdat_path_input.disabled = disabled or norm_picker_mode
        shell.normalization_validate_button.disabled = disabled
        shell.normalization_import_confirm_button.disabled = disabled
        shell.normalization_import_cancel_button.disabled = disabled
        shell.normalization_adopt_confirm_button.disabled = disabled
        shell.normalization_adopt_cancel_button.disabled = disabled
        shell.normalization_context_select.disabled = disabled
        shell.normalization_custom_files_switch.disabled = disabled
        if hasattr(shell, "normalization_custom_files_toggle_button"):
            shell.normalization_custom_files_toggle_button.disabled = disabled
        if hasattr(shell, "_refresh_normalization_fit_params_button_states"):
            shell._refresh_normalization_fit_params_button_states()
        if hasattr(shell, "_sync_normalization_fit_params_export_prompt_visibility"):
            shell._sync_normalization_fit_params_export_prompt_visibility()

    if is_background_tab and hasattr(shell, "_refresh_background_export_hovercard"):
        shell._refresh_background_export_hovercard()
    if hasattr(shell, "_sync_background_export_prompt_visibility"):
        shell._sync_background_export_prompt_visibility()
    if hasattr(shell, "_sync_ft_real_space_export_prompt_visibility"):
        shell._sync_ft_real_space_export_prompt_visibility()

    # Back Fourier Transform (BFT) global disable rules (operation_in_progress blocks switching/workflow).
    # Note: When not disabled, BFT controller code owns enabling/disabling based on context readiness.
    if disabled:
        for name in (
            "bft_context_select",
            "bft_iterations_input",
            "bft_run_button",
            "bft_iterations_confirm_button",
            "bft_iterations_cancel_button",
            "bft_animation_player",
            "bft_final_prev_plot_button",
            "bft_final_next_plot_button",
        ):
            w = getattr(shell, name, None)
            if w is None:
                continue
            try:
                w.disabled = True
            except Exception:
                pass


def refresh_workspace_button_states(shell) -> None:
    for tab_name, button in shell.workspace_buttons.items():
        button.button_type = "primary" if tab_name == shell.current_top_level_tab else "light"


def show_workspace_blocked_message(shell) -> None:
    shell.workspace_message.object = (
        "An operation is in progress. This action is blocked until it finishes."
    )
    shell.workspace_message.alert_type = "warning"
    shell.workspace_message.visible = True
    if shell.current_screen == "workspace":
        shell._refresh_interaction_states()


def clear_workspace_message(shell) -> None:
    shell.workspace_message.object = ""
    shell.workspace_message.visible = False


def show_toast(
    shell,
    *,
    level: ToastLevel,
    message: str,
    persistent: bool | None = None,
) -> None:
    if persistent is None:
        persistent = level == "error"

    if persistent:
        duration_ms = 0
    elif level == "success":
        duration_ms = int(getattr(shell, "toast_success_duration_ms", 5000))
    elif level == "info":
        duration_ms = int(getattr(shell, "toast_info_duration_ms", 6000))
    else:
        duration_ms = int(getattr(shell, "toast_duration_ms", 8000))
        
    area = pn.state.notifications
    if area is None:
        return
    if level == "success":
        area.success(message, duration=duration_ms)
    elif level == "warning":
        area.warning(message, duration=duration_ms)
    elif level == "error":
        area.error(message, duration=duration_ms)
    else:
        area.info(message, duration=duration_ms)


def show_success_toast(shell, message: str) -> None:
    show_toast(shell, level="success", message=message, persistent=False)


def show_info_toast(shell, message: str) -> None:
    show_toast(shell, level="info", message=message, persistent=False)


def show_warning_toast(shell, message: str) -> None:
    show_toast(shell, level="warning", message=message, persistent=False)


def show_error_toast(shell, message: str) -> None:
    show_toast(shell, level="error", message=message, persistent=True)


def clear_success_toast_if_current(shell, _token: int) -> None:
    return


def build_template(shell) -> pn.template.FastListTemplate:
    return pn.template.FastListTemplate(
        title="ToScaNA",
        main=[shell.content],
        header=[
            pn.Spacer(),
            pn.Spacer(),
            shell.reset_project_button,
        ],
    )
