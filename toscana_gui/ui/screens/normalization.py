from __future__ import annotations

import panel as pn

_QUICK_GUIDE_TOOLTIP_HTML = """\
<div style="max-width: 320px; line-height: 1.45; white-space: normal; overflow-wrap: anywhere; word-break: break-word;">
  <p style="margin: 0 0 10px 0;">
    To perform normalization, we must isolate the self scattering of vanadium. Numerically, the steps to follow are:
  </p>
  <ol style="margin: 0; padding-left: 20px;">
    <li>Select Fitting Data</li>
    <li>Select Fitting Parameters</li>
    <li>Run Fit</li>
    <li>Repeat Steps 1 and 2 if Needed</li>
    <li>Normalize the Sample</li>
    <li>Export Data</li>
  </ol>
</div>
"""


def build_normalization_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Normalization.",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    # NOTE: Avoid mutating widget values during render; refresh only the dropdown options.
    if hasattr(shell, "_refresh_normalization_qdat_dropdown_options"):
        shell._refresh_normalization_qdat_dropdown_options()
    if hasattr(shell, "_refresh_normalization_context_options"):
        shell._refresh_normalization_context_options(apply_selection=False)
    if hasattr(shell, "_refresh_normalization_context_summary"):
        shell._refresh_normalization_context_summary()
    if hasattr(shell, "_refresh_normalization_sample_normalization_plot"):
        shell._refresh_normalization_sample_normalization_plot()
    if hasattr(shell, "_sync_normalization_custom_files_ui"):
        shell._sync_normalization_custom_files_ui()

    resolved_context_notice = _maybe_toast_only(
        shell,
        key="normalization:resolved_context_message",
        pane=shell.normalization_context_message,
    )

    selection_notice = _maybe_toast_only(
        shell,
        key="normalization:selection_message",
        pane=shell.normalization_selection_message,
    )

    show_custom = bool(getattr(shell.normalization_custom_files_switch, "value", False))
    shell.normalization_context_select.name = ""
    shell.normalization_source_mode.name = "Create Custom Context"

    resolved_context_content = pn.Column(
        pn.Row(
            shell.normalization_context_select,
            shell.normalization_context_info_hover,
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
        ),
        resolved_context_notice,
        shell.normalization_context_summary,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
        visible=not show_custom,
    )

    custom_files_content = pn.Column(
        shell.normalization_source_mode,
        shell.normalization_source_stack,
        pn.Row(shell.normalization_validate_button, sizing_mode="stretch_width"),
        selection_notice,
        shell.normalization_import_card,
        shell.normalization_adopt_card,
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
        visible=show_custom,
    )
    data_source_card = pn.Card(
        pn.FlexBox(
            resolved_context_content,
            custom_files_content,
            pn.Column(
                pn.Spacer(height=20),
                pn.Row(
                    shell.normalization_custom_files_toggle_button,
                    sizing_mode="stretch_width",
                    styles={"justify-content": "center"},
                ),
                sizing_mode="stretch_width",
                styles={"flex": "0 1 280px"},
            ),
            gap="18px",
            flex_wrap="wrap",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-source-header"],
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Current Data Selection Mode</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            shell.normalization_custom_files_state_badge,
            sizing_mode="stretch_width",
            styles={"align-items": "center", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header", "toscana-normalization-source-card-header--mode"],
        ),
        sizing_mode="stretch_width",
        css_classes=[
            "toscana-overflow-visible",
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
        ],
    )

    quick_guide_toggle = pn.widgets.TooltipIcon(
        value=_QUICK_GUIDE_TOOLTIP_HTML,
        width=36,
        height=36,
        align="center",
        margin=(0, 0, 0, 0),
        styles={"color": "rgb(220, 38, 38)"},
        css_classes=["toscana-normalization-guide-tooltip"],
    )

    vanadium_fit_card = pn.Card(
        pn.Spacer(height=0),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Vanadium Fit</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            quick_guide_toggle,
            pn.Spacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header"],
        ),
        sizing_mode="stretch_width",
        collapsible=False,
        margin=(0, 0, 0, 0),
        css_classes=[
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
            "toscana-normalization-vanadium-fit-card",
        ],
    )

    select_fitting_data_redesign_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=150),
                    shell.normalization_fit_data_redesign_vertical_axis_controls,
                    pn.Spacer(height=75),
                    sizing_mode="fixed",
                    width=206,
                    height=600,
                    margin=(0, 0, 0, 0),
                    styles={"align-items": "center"},
                ),
                pn.Column(
                    shell.normalization_fit_data_redesign_top_controls,
                    pn.Spacer(height=10),
                    pn.Row(
                        pn.Column(
                            shell.normalization_fit_data_redesign_plot_pane,
                            sizing_mode="fixed",
                            width=800,
                            height=600,
                            styles={"flex": "0 0 800px", "overflow": "hidden"},
                        ),
                        pn.Column(
                            shell.normalization_fit_data_redesign_right_tray,
                            sizing_mode="fixed",
                            width=320,
                            styles={"flex": "0 0 320px", "min-width": "320px"},
                        ),
                        sizing_mode="fixed",
                        width=1144,
                        styles={"align-items": "flex-start", "gap": "14px", "position": "relative"},
                    ),
                    pn.Row(
                        pn.Spacer(width=100),
                        shell.normalization_fit_data_redesign_horizontal_axis_controls,
                        pn.Spacer(width=100),
                        sizing_mode="fixed",
                        width=800,
                        margin=(14, 0, 0, 0),
                        styles={"gap": "0px"},
                    ),
                    sizing_mode="fixed",
                    width=1144,
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto"},
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Select Fitting Data</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            shell.normalization_fit_data_redesign_mode_chips,
            sizing_mode="stretch_width",
            styles={"align-items": "center", "justify-content": "space-between", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header"],
        ),
        sizing_mode="stretch_width",
        collapsible=False,
        margin=(0, 0, 0, 0),
        css_classes=[
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
        ],
    )

    select_fitting_parameters_redesign_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Row(
                    shell.normalization_fit_params_suggest_button,
                    sizing_mode="fixed",
                    width=320,
                    height=40,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    shell.normalization_fit_params_run_button,
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=800,
                    height=40,
                    styles={"align-items": "center"},
                ),
                pn.Row(
                    shell.normalization_fit_params_export_button,
                    sizing_mode="fixed",
                    width=320,
                    height=40,
                    styles={"justify-content": "flex-end", "align-items": "center"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "center", "gap": "14px"},
            ),
            pn.Spacer(height=16),
            pn.Row(
                 pn.Column(
                     shell.normalization_fit_params_status_card,
                     shell.normalization_fit_params_core_polynomial,
                     shell.normalization_fit_params_core_inelastic,
                     shell.normalization_fit_params_bounds_toggle,
                     sizing_mode="fixed",
                     width=320,
                     styles={"gap": "12px"},
                     css_classes=["toscana-fit-params-sidecolumn"],
                 ),
                 pn.Column(
                    pn.Row(
                        pn.Spacer(),
                        shell.normalization_vanadium_self_fit_preview_view_selector,
                        sizing_mode="fixed",
                        width=800,
                        height=34,
                        styles={"align-items": "center", "justify-content": "flex-end"},
                    ),
                     pn.Spacer(height=10),
                     shell.normalization_vanadium_self_fit_preview_plot_pane,
                     shell.normalization_fit_params_bounds_card,
                     sizing_mode="fixed",
                     width=800,
                     styles={"overflow": "hidden"},
                 ),
                pn.Column(
                    pn.Spacer(height=44),
                    shell.normalization_vanadium_self_fit_preview_fit_table,
                    pn.Spacer(height=12),
                    shell.normalization_fit_params_export_prompt_card,
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto"},
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Select Fitting Parameters</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            pn.Spacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center", "justify-content": "space-between", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header"],
        ),
        sizing_mode="stretch_width",
        collapsible=False,
        margin=(0, 0, 0, 0),
        css_classes=[
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
        ],
    )

    sample_normalization_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=320,
                    height=40,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=800,
                    height=40,
                    styles={"align-items": "center"},
                ),
                pn.Row(
                    shell.normalization_sample_norm_export_button,
                    sizing_mode="fixed",
                    width=320,
                    height=40,
                    styles={"justify-content": "flex-end", "align-items": "center"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "center", "gap": "14px"},
            ),
            pn.Spacer(height=16),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=44),
                    sizing_mode="fixed",
                    width=320,
                ),
                pn.Column(
                    shell.normalization_sample_norm_plot_pane,
                    sizing_mode="fixed",
                    width=800,
                    styles={"overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    shell.normalization_sample_norm_export_prompt_card,
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto"},
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Sample Normalization</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            pn.Spacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center", "justify-content": "space-between", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header"],
        ),
        sizing_mode="stretch_width",
        collapsible=False,
        margin=(0, 0, 0, 0),
        css_classes=[
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
        ],
    )

    return pn.Column(
        data_source_card,
        pn.Spacer(height=22),
        vanadium_fit_card,
        pn.Spacer(height=12),
        select_fitting_data_redesign_card,
        pn.Spacer(height=12),
        select_fitting_parameters_redesign_card,
        pn.Spacer(height=12),
        sample_normalization_card,
        sizing_mode="stretch_width",
    )


def _maybe_toast_only(shell, *, key: str, pane: pn.pane.Alert) -> object:
    message = str(getattr(pane, "object", "") or "").strip()
    alert_type = str(getattr(pane, "alert_type", "secondary") or "secondary")
    if not message:
        pane.visible = False
        return pn.Spacer(height=0)

    level_map = {
        "primary": "info",
        "secondary": "info",
        "success": "success",
        "warning": "warning",
        "danger": "error",
    }
    level = level_map.get(alert_type, "info")
    pane.visible = False
    if hasattr(shell, "_show_toast_once"):
        shell._show_toast_once(
            key,
            level=level,
            message=message,
            persistent=alert_type == "danger",
        )
    return pn.Spacer(height=0)
