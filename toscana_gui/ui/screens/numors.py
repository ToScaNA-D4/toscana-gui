from __future__ import annotations

from html import escape

import panel as pn


def prepare_numors_section(shell) -> None:
    if getattr(shell, "_numors_section_layout", None) is not None:
        _refresh_numors_section_state(shell)
        return

    def _go_to_run_history(_event=None) -> None:
        shell._navigate_to_workspace_section("run_history")

    shell._numors_run_history_info_button = pn.widgets.Button(
        name="Run History",
        button_type="light",
        width=140,
        height=40,
    )
    shell._numors_run_history_info_button.on_click(_go_to_run_history)

    shell._numors_selection_left_column = pn.Column(
        shell.numors_source_mode,
        shell.numors_source_stack,
        pn.Spacer(height=12),
        pn.Row(
            shell.numors_validate_button,
            shell.numors_run_button,
            shell.numors_validation_info_hover,
            sizing_mode="stretch_width",
            styles={"align-items": "center", "gap": "12px", "flex-wrap": "wrap"},
        ),
        shell.numors_message,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
    )
    shell._numors_selection_right_spacer = pn.Column(
        pn.Spacer(height=20),
        sizing_mode="stretch_width",
        styles={"flex": "0 1 280px"},
    )
    shell._numors_selection_body = pn.FlexBox(
        shell._numors_selection_left_column,
        shell._numors_selection_right_spacer,
        gap="18px",
        flex_wrap="wrap",
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-source-header"],
    )
    shell._numors_selection_card = pn.Card(
        shell._numors_selection_body,
        title="Numors .par Selection",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
    )
    shell._numors_run_history_footer = pn.Row(
        pn.pane.Markdown(
            "Need logs or plots? Open the Run History tab.",
            sizing_mode="stretch_width",
            margin=(0, 0, 0, 0),
        ),
        pn.Spacer(),
        shell._numors_run_history_info_button,
        sizing_mode="stretch_width",
    )
    shell._numors_section_layout = pn.Column(
        shell._numors_selection_card,
        shell.numors_import_card,
        pn.Spacer(height=16),
        shell.numors_run_blocks_card,
        shell._numors_run_history_footer,
        sizing_mode="stretch_width",
    )
    _refresh_numors_section_state(shell)


def build_numors_section(shell) -> pn.Column:
    prepare_numors_section(shell)
    return shell._numors_section_layout


def _refresh_numors_section_state(shell) -> None:
    numors_state = shell._get_numors_state()
    validation_state = numors_state["validation"]

    if hasattr(shell, "_set_numors_source_widget_visibility"):
        shell._set_numors_source_widget_visibility()
    if hasattr(shell, "_sync_numors_import_visibility"):
        shell._sync_numors_import_visibility()

    has_numors_run = _has_numors_run(shell)
    if hasattr(shell, "numors_validation_info_hover"):
        shell.numors_validation_info_hover.visible = has_numors_run
        shell.numors_validation_info_hover.value = (
            _build_validation_tooltip_html(validation_state) if has_numors_run else ""
        )

    latest_record = _latest_numors_record(shell)
    if hasattr(shell, "_refresh_numors_run_blocks_view"):
        shell._refresh_numors_run_blocks_view(latest_record)


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
