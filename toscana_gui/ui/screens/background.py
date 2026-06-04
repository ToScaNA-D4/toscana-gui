from __future__ import annotations

from html import escape

import panel as pn


def build_background_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Sample extraction.",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    if hasattr(shell, "_set_background_source_widget_visibility"):
        shell._set_background_source_widget_visibility()

    background_state = shell._get_background_state() if hasattr(shell, "_get_background_state") else {}
    validation_state = (
        background_state.get("validation", {})
        if isinstance(background_state, dict)
        else {}
    )

    has_background_run = _has_background_extract_run(shell)
    validation_hovercard = (
        shell.background_validation_info_hover
        if has_background_run and hasattr(shell, "background_validation_info_hover")
        else pn.Spacer(width=0, height=0)
    )
    if has_background_run and hasattr(shell, "background_validation_info_hover"):
        shell.background_validation_info_hover.value = _build_validation_tooltip_html(validation_state)

    background_notice = _maybe_inline_or_toast(
        shell,
        key="background:message",
        pane=shell.background_message,
    )

    selection_left_column = pn.Column(
        shell.background_source_mode,
        shell.background_source_stack,
        pn.Spacer(height=12),
        pn.Row(
            shell.background_validate_button,
            shell.background_extract_button,
            validation_hovercard,
            sizing_mode="stretch_width",
            styles={"align-items": "center", "gap": "12px", "flex-wrap": "wrap"},
        ),
        background_notice,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
    )
    selection_right_spacer = pn.Column(
        pn.Spacer(height=20),
        sizing_mode="stretch_width",
        styles={"flex": "0 1 280px"},
    )
    selection_body = pn.FlexBox(
        selection_left_column,
        selection_right_spacer,
        gap="18px",
        flex_wrap="wrap",
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-source-header"],
    )

    contents: list[object] = [
        pn.Card(
            selection_body,
            title="Sample Extraction",
            sizing_mode="stretch_width",
            css_classes=["toscana-overflow-visible"],
        )
    ]

    contents.append(shell.background_import_card)

    # Add whitespace between the sample extraction area and the next header.
    contents.append(pn.Spacer(height=16))

    if hasattr(shell, "_refresh_background_plots"):
        shell._refresh_background_plots()

    contents.extend(
        [
            shell.background_no_data_pane,
            shell.background_raw_plot_alert,
            shell.background_raw_plot_card,
            pn.Spacer(height=16),
            shell.background_subtraction_sample_card,
            pn.Spacer(height=16),
        ]
    )

    contents.extend(
        [
            shell.background_subtraction_vanadium_card,
            pn.Spacer(height=16),
            shell.background_final_signals_plot_card,
            pn.Spacer(height=16),
            shell.background_export_card,
        ]
    )

    return pn.Column(*contents, sizing_mode="stretch_width")


def _has_background_extract_run(shell) -> bool:
    if shell.current_project_state is None:
        return False
    return any(record.workflow == "background_extract" for record in shell.current_project_state.runs)


def _format_yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


def _fmt_path(value: object) -> str:
    raw = str(value).strip() if value is not None else ""
    if not raw:
        return "<em>Not available</em>"
    return (
        "<code style=\"white-space: normal; overflow-wrap: anywhere; "
        "word-break: break-word;\">"
        f"{escape(raw)}"
        "</code>"
    )


def _build_validation_tooltip_html(validation_state: dict) -> str:
    selected_file = _fmt_path(validation_state.get("selected_par_path"))
    accessible = _format_yes_no(validation_state.get("file_accessible"))
    is_valid = _format_yes_no(validation_state.get("is_valid"))
    error_raw = str(validation_state.get("error") or "").strip()
    error_html = _fmt_path(error_raw) if error_raw else "<em>None</em>"

    return f"""
    <div style="max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;">
      <div><strong>Selected file:</strong> {selected_file}</div>
      <div><strong>File accessible:</strong> {escape(accessible)}</div>
      <div><strong>Valid:</strong> {escape(is_valid)}</div>
      <div><strong>Error:</strong> {error_html}</div>
    </div>
    """.strip()


def _maybe_inline_or_toast(shell, *, key: str, pane: pn.pane.Alert) -> object:
    message = str(getattr(pane, "object", "") or "").strip()
    alert_type = str(getattr(pane, "alert_type", "secondary") or "secondary")
    if not message:
        return pn.Spacer(height=0)

    level_map = {
        "primary": "info",
        "secondary": "info",
        "success": "success",
        "warning": "warning",
        "danger": "error",
    }
    level = level_map.get(alert_type, "info")
    pane.visible = alert_type == "danger"
    if alert_type != "danger":
        shell._show_toast_once(key, level=level, message=message, persistent=False)
        return pn.Spacer(height=0)

    shell._show_toast_once(key, level=level, message=message, persistent=True)
    return pane
