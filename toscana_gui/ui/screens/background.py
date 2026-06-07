from __future__ import annotations

from html import escape

import panel as pn

def prepare_background_section(shell) -> None:
    """
    Create the skeleton of all elements in the background tab section
    """
    if getattr(shell, "_background_section_layout", None):
        # this means it's already built so we just refresh to a mutable state
        _refresh_background_section_state(shell)
        return 
    
    shell._background_button_row = pn.Row(
        shell.background_validate_button,
        shell.background_extract_button,
        shell.background_validation_info_hover,
        sizing_mode="stretch_width",
        styles={"align-items": "center", "gap": "12px", "flex-wrap": "wrap"}, 
    )

    shell._background_selection_column = pn.Column(
        shell.background_source_mode, 
        shell.background_source_stack,
        pn.Spacer(height=12),
        shell._background_button_row,
        shell.background_message,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
    )

    shell._background_selection_card = pn.Card(
        pn.FlexBox(
            shell._background_selection_column, 
            pn.Column(pn.Spacer(height=20), sizing_mode="stretch_width", 
                      styles={"flex": "0 1 280px"}),
            gap="18px",
            flex_wrap="wrap",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-source-header"],
        ),
        title="Sample Extraction",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
    )

    shell._background_section_layout = pn.Column(
        shell._background_selection_card, 
        shell.background_import_card, 
        pn.Spacer(height=16),
        shell.background_no_data_pane,
        shell.background_raw_plot_alert,
        shell.background_raw_plot_card,
        pn.Spacer(height=16),
        shell.background_subtraction_sample_card,
        pn.Spacer(height=16),
        shell.background_subtraction_vanadium_card,
        pn.Spacer(height=16),
        shell.background_final_signals_plot_card,
        pn.Spacer(height=16),
        shell.background_export_card, 
        sizing_mode="stretch_width",
    )
    _refresh_background_section_state(shell)


def refresh_background_section_state(shell) -> None:
    _refresh_background_section_state(shell)


def _refresh_background_section_state(shell) -> None:
    """
    Update the mutable parts of the background section 
    """

    if hasattr(shell, "_set_background_source_widget_visibility"):
        shell._set_background_source_widget_visibility()
    
    has_background_run = _has_background_extract_run(shell)
    if hasattr(shell, "background_validation_info_hover"):
        shell.background_validation_info_hover.visible = has_background_run
        if has_background_run:
            background_state = shell._get_background_state() if hasattr(shell, "_get_background_state") else {}
            validation_state = background_state.get("validation", {}) if isinstance(background_state, dict) else {}
            shell.background_validation_info_hover.value = _build_validation_tooltip_html(validation_state)

def build_background_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Sample extraction.",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    prepare_background_section(shell)
    return shell._background_section_layout


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

