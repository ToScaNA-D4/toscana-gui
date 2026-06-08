from __future__ import annotations

import panel as pn


def build_self_scattering_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Self Scattering.",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    # NOTE: Avoid mutating widget values during render; refresh only the dropdown options/summary.
    if hasattr(shell, "_refresh_self_context_options"):
        shell._refresh_self_context_options(apply_selection=False)
    if hasattr(shell, "_refresh_self_context_summary"):
        shell._refresh_self_context_summary()
    if hasattr(shell, "_refresh_self_lowq_panel"):
        shell._refresh_self_lowq_panel()
    if hasattr(shell, "_refresh_self_data_selection_panel"):
        shell._refresh_self_data_selection_panel()
    if hasattr(shell, "_refresh_self_fit_panel"):
        shell._refresh_self_fit_panel()
    if hasattr(shell, "_refresh_self_export_hovercard"):
        shell._refresh_self_export_hovercard()
    if hasattr(shell, "_refresh_self_export_button_states"):
        shell._refresh_self_export_button_states()

    resolved_context_notice = _maybe_toast_only(
        shell,
        key="self_scattering:resolved_context_message",
        pane=getattr(shell, "self_context_message", None),
    )

    data_source_card = pn.Card(
        pn.FlexBox(
            pn.Column(
                pn.Row(
                    shell.self_context_select,
                    shell.self_context_info_hover,
                    sizing_mode="stretch_width",
                    styles={"align-items": "center"},
                ),
                resolved_context_notice,
                shell.self_context_summary,
                sizing_mode="stretch_width",
                styles={"flex": "1 1 520px"},
            ),
            # Keep the exact same right-side column width as the Normalization header area
            # so the dropdown sizing/position matches visually.
            pn.Column(
                pn.Spacer(height=20),
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

    # Shift the low-Q and data-selection cards so their plot anchors line up
    # with the Fit Model / Static Structure Factor reference cards (320px left gutter).
    self_plot_left_margin_px = 320 - 206
    lowq_card = pn.Card(
        pn.Column(
            pn.Spacer(height=6),
            pn.Row(
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
                objects=[
                    pn.Column(
                        pn.Spacer(height=150),
                        getattr(shell, "self_lowq_redesign_vertical_axis_controls", pn.Spacer(height=0)),
                        pn.Spacer(height=75),
                        sizing_mode="fixed",
                        width=206,
                        height=600,
                        margin=(0, 0, 0, 0),
                        styles={"align-items": "center"},
                    ),
                    pn.Column(
                        pn.Spacer(height=10),
                        pn.Row(
                            pn.Column(
                                pn.Column(
                                    # Outer wrapper: allow overlay to extend without being clipped.
                                    # Inner plot clipper: keep Plotly canvas contained.
                                    pn.Column(
                                        getattr(shell, "self_lowq_redesign_top_controls", pn.Spacer(height=0)),
                                        sizing_mode="fixed",
                                        width=800,
                                        height=62,
                                        margin=(0, 0, 0, 0),
                                        styles={
                                            "position": "absolute",
                                            "top": "0px",
                                            "left": "0px",
                                            "right": "0px",
                                            "z-index": "20",
                                            "pointer-events": "auto",
                                        },
                                    ),
                                    pn.Column(
                                        getattr(shell, "self_lowq_view_selector", pn.Spacer(height=0)),
                                        sizing_mode="fixed",
                                        width=800,
                                        height=34,
                                        margin=(0, 0, 0, 0),
                                        styles={
                                            "position": "absolute",
                                            "top": "62px",
                                            "left": "0px",
                                            "right": "0px",
                                            "z-index": "30",
                                            "pointer-events": "auto",
                                        },
                                    ),
                                    pn.Column(
                                        getattr(shell, "self_lowq_redesign_plot_pane", pn.Spacer(height=0)),
                                        sizing_mode="fixed",
                                        width=800,
                                        height=600,
                                        margin=(96, 0, 0, 0),
                                        styles={
                                            "overflow": "hidden",
                                            "box-sizing": "border-box",
                                        },
                                    ),
                                    sizing_mode="fixed",
                                    width=800,
                                    height=696,
                                    margin=(0, 0, 0, 0),
                                    styles={
                                        "position": "relative",
                                        "overflow": "visible",
                                    },
                                ),
                                sizing_mode="fixed",
                                width=800,
                                styles={"flex": "0 0 800px", "overflow": "hidden"},
                            ),
                            pn.Column(
                                pn.Spacer(height=150),
                                getattr(shell, "self_lowq_redesign_window_table", pn.Spacer(height=0)),
                                pn.Spacer(),
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
                            getattr(shell, "self_lowq_redesign_horizontal_axis_controls", pn.Spacer(height=0)),
                            pn.Spacer(width=100),
                            sizing_mode="fixed",
                            width=800,
                            margin=(14, 0, 0, 0),
                            styles={"gap": "0px"},
                        ),
                        sizing_mode="fixed",
                        width=1144,
                    ),
                ],
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto", "padding-left": f"{self_plot_left_margin_px}px"},
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Sample Extrapolation to Low Q</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            getattr(shell, "self_lowq_redesign_mode_chips", pn.Spacer(height=0)),
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

    data_selection_card = pn.Card(
        pn.Column(
            pn.Spacer(height=6),
            pn.Row(
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
                objects=[
                    pn.Column(
                        pn.Spacer(height=150),
                        getattr(shell, "self_data_selection_redesign_vertical_axis_controls", pn.Spacer(height=0)),
                        pn.Spacer(height=75),
                        sizing_mode="fixed",
                        width=206,
                        height=600,
                        margin=(0, 0, 0, 0),
                        styles={"align-items": "center"},
                    ),
                    pn.Column(
                        getattr(shell, "self_data_selection_redesign_top_controls", pn.Spacer(height=0)),
                        pn.Spacer(height=10),
                        pn.Row(
                            pn.Column(
                                getattr(shell, "self_data_selection_redesign_plot_pane", pn.Spacer(height=0)),
                                sizing_mode="fixed",
                                width=800,
                                height=600,
                                styles={"flex": "0 0 800px", "overflow": "hidden"},
                            ),
                            pn.Column(
                                pn.Spacer(height=150),
                                getattr(shell, "self_data_selection_redesign_window_table", pn.Spacer(height=0)),
                                pn.Spacer(),
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
                            getattr(shell, "self_data_selection_redesign_horizontal_axis_controls", pn.Spacer(height=0)),
                            pn.Spacer(width=100),
                            sizing_mode="fixed",
                            width=800,
                            margin=(14, 0, 0, 0),
                            styles={"gap": "0px"},
                        ),
                        sizing_mode="fixed",
                        width=1144,
                    ),
                ],
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto", "padding-left": f"{self_plot_left_margin_px}px"},
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Data Selection</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            getattr(shell, "self_data_selection_redesign_mode_chips", pn.Spacer(height=0)),
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

    fit_model_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Spacer(width=320),
                pn.Column(
                    pn.Row(
                        pn.layout.HSpacer(),
                        pn.Row(
                            getattr(shell, "self_fit_model_selector", pn.Spacer(height=0)),
                            getattr(shell, "self_fit_model_info_hover", pn.Spacer(height=0)),
                            sizing_mode="fixed",
                            styles={"align-items": "center"},
                        ),
                        pn.layout.HSpacer(),
                        sizing_mode="fixed",
                        width=800,
                        styles={"align-items": "center"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                    styles={"align-items": "center", "gap": "0px"},
                ),
                pn.Spacer(width=320),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto"},
            ),
            pn.Spacer(height=14),
            pn.Row(
                pn.Row(
                    getattr(shell, "self_fit_params_suggest_button", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    height=40,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    getattr(shell, "self_fit_params_run_button", pn.Spacer(height=0)),
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=800,
                    height=40,
                    styles={"align-items": "center"},
                ),
                pn.Row(
                    pn.Spacer(width=0),
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
                    getattr(shell, "self_fit_params_status", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_alert", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_vana_section", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_poly_section", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_lorgau_section", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_bounds_toggle", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                    css_classes=["toscana-fit-params-sidecolumn"],
                ),
                pn.Column(
                    pn.Spacer(height=10),
                    getattr(shell, "self_fit_plot_pane", pn.Spacer(height=0)),
                    getattr(shell, "self_fit_params_bounds_card", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    styles={"overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    getattr(shell, "self_fit_result_table", pn.Spacer(height=0)),
                    pn.Spacer(height=12),
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            sizing_mode="stretch_width",
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Fit Model</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            sizing_mode="stretch_width",
            styles={"align-items": "center", "justify-content": "flex-start", "gap": "12px"},
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

    static_structure_factor_card = pn.Card(
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
                    pn.Spacer(width=0),
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
                    getattr(shell, "self_static_structure_factor_summary_table", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                pn.Column(
                    getattr(shell, "self_static_structure_factor_plot_pane", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    styles={"overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    pn.Spacer(height=0),
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
                "<h3>Static Structure Factor</h3>",
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
        pn.Spacer(height=18),
        lowq_card,
        pn.Spacer(height=18),
        data_selection_card,
        pn.Spacer(height=28),
        fit_model_card,
        pn.Spacer(height=28),
        static_structure_factor_card,
        pn.Spacer(height=16),
        getattr(shell, "self_export_card", pn.Spacer(height=0)),
        sizing_mode="stretch_width",
    )


def _maybe_toast_only(shell, *, key: str, pane: object) -> object:
    if pane is None:
        return pn.Spacer(height=0)
    message = str(getattr(pane, "object", "") or "").strip()
    if not message:
        return pn.Spacer(height=0)
    alert_type = str(getattr(pane, "alert_type", "secondary") or "secondary")

    level_map = {
        "primary": "info",
        "secondary": "info",
        "success": "success",
        "warning": "warning",
        "danger": "error",
    }
    level = level_map.get(alert_type, "info")
    if hasattr(shell, "_show_toast_once"):
        shell._show_toast_once(key, level=level, message=message, persistent=alert_type == "danger")

    # Render inline only for danger; otherwise toast-only to keep the layout tidy.
    try:
        pane.visible = alert_type == "danger"
    except Exception:
        pass
    return pane if alert_type == "danger" else pn.Spacer(height=0)
