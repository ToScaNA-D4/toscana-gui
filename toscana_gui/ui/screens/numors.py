from __future__ import annotations

from html import escape

import panel as pn


def build_numors_section(shell) -> pn.Column:
    numors_state = shell._get_numors_state()
    validation_state = numors_state["validation"]

    if hasattr(shell, "_set_numors_source_widget_visibility"):
        shell._set_numors_source_widget_visibility()

    def _go_to_run_history(_event=None) -> None:
        shell._navigate_to_workspace_section("run_history")

    run_history_info_button = pn.widgets.Button(
        name="Run History",
        button_type="light",
        width=140,
        height=40,
    )
    run_history_info_button.on_click(_go_to_run_history)

    has_numors_run = _has_numors_run(shell)
    validation_hovercard = shell.numors_validation_info_hover if has_numors_run else pn.Spacer(width=0, height=0)
    if has_numors_run and hasattr(shell, "numors_validation_info_hover"):
        shell.numors_validation_info_hover.value = _build_validation_tooltip_html(validation_state)

    numors_notice = _maybe_inline_or_toast(
        shell,
        key="numors:message",
        pane=shell.numors_message,
    )

    selection_left_column = pn.Column(
        shell.numors_source_mode,
        shell.numors_source_stack,
        pn.Spacer(height=12),
        pn.Row(
            shell.numors_validate_button,
            shell.numors_run_button,
            validation_hovercard,
            sizing_mode="stretch_width",
            styles={"align-items": "center", "gap": "12px", "flex-wrap": "wrap"},
        ),
        numors_notice,
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
            title="Numors .par Selection",
            sizing_mode="stretch_width",
            css_classes=["toscana-overflow-visible"],
        )
    ]

    contents.append(shell.numors_import_card)

    # Add whitespace between the Numors selection area and the next header ("Run Blocks").
    contents.append(pn.Spacer(height=16))

    latest_record = _latest_numors_record(shell)
    shell._refresh_numors_run_blocks_view(latest_record)
    if shell.numors_run_blocks_card.visible:
        contents.append(shell.numors_run_blocks_card)

    contents.append(
        pn.Row(
            pn.pane.Markdown(
                "Need logs or plots? Open the Run History tab.",
                sizing_mode="stretch_width",
                margin=(0, 0, 0, 0),
            ),
            pn.Spacer(),
            run_history_info_button,
            sizing_mode="stretch_width",
        )
    )

    return pn.Column(
        *contents,
        sizing_mode="stretch_width",
    )


def _has_numors_run(shell) -> bool:
    if shell.current_project_state is None:
        return False
    return any(record.workflow == "numors" for record in shell.current_project_state.runs)


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

def _build_validation_hovercard_html(validation_state: dict) -> str:
    selected_file = _fmt_path(validation_state.get("selected_par_path"))
    accessible = _format_yes_no(validation_state.get("file_accessible"))
    rawdata_path = _fmt_path(validation_state.get("resolved_rawdata_path"))
    eff_path = _fmt_path(validation_state.get("resolved_efffile_path"))
    dec_path = _fmt_path(validation_state.get("resolved_decfile_path"))

    return f"""
    <div class="toscana-hovercard toscana-hovercard--open-right" aria-label="Validation summary">
      <div class="toscana-hovercard__icon" title="Validation summary">?</div>
      <div class="toscana-hovercard__panel">
        <div><strong>Selected file:</strong> {selected_file}</div>
        <div><strong>File accessible:</strong> {escape(accessible)}</div>
        <div><strong>Resolved raw data path:</strong> {rawdata_path}</div>
        <div><strong>Resolved efficiency path:</strong> {eff_path}</div>
        <div><strong>Resolved shifts path:</strong> {dec_path}</div>
      </div>
    </div>
    """.strip()


def _build_validation_tooltip_html(validation_state: dict) -> str:
    selected_file = _fmt_path(validation_state.get("selected_par_path"))
    accessible = _format_yes_no(validation_state.get("file_accessible"))
    rawdata_path = _fmt_path(validation_state.get("resolved_rawdata_path"))
    eff_path = _fmt_path(validation_state.get("resolved_efffile_path"))
    dec_path = _fmt_path(validation_state.get("resolved_decfile_path"))

    return f"""
    <div style="max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;">
      <div><strong>Selected file:</strong> {selected_file}</div>
      <div><strong>File accessible:</strong> {escape(accessible)}</div>
      <div><strong>Resolved raw data path:</strong> {rawdata_path}</div>
      <div><strong>Resolved efficiency path:</strong> {eff_path}</div>
      <div><strong>Resolved shifts path:</strong> {dec_path}</div>
    </div>
    """.strip()


def _latest_numors_record(shell):
    if shell.current_project_state is None:
        return None

    return next(
        (record for record in reversed(shell.current_project_state.runs) if record.workflow == "numors"),
        None,
    )


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
