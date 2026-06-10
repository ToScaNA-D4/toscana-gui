from __future__ import annotations

import panel as pn


def build_ft_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Fourier Transform (FT).",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    # NOTE: Avoid mutating widget values during render; refresh only the dropdown options/summary.
    if hasattr(shell, "_refresh_ft_context_options"):
        shell._refresh_ft_context_options(apply_selection=False)
    if hasattr(shell, "_refresh_ft_context_summary"):
        shell._refresh_ft_context_summary()
    if hasattr(shell, "_load_ft_soq_series"):
        shell._load_ft_soq_series()
    if hasattr(shell, "_refresh_ft_base_gr_panel"):
        shell._refresh_ft_base_gr_panel()
    if hasattr(shell, "_refresh_ft_effective_atomic_density_panel"):
        shell._refresh_ft_effective_atomic_density_panel()
    if hasattr(shell, "_refresh_ft_export_hovercard"):
        shell._refresh_ft_export_hovercard()
    if hasattr(shell, "_refresh_ft_export_button_states"):
        shell._refresh_ft_export_button_states()

    resolved_context_notice = _maybe_toast_only(
        shell,
        key="ft:resolved_context_message",
        pane=getattr(shell, "ft_context_message", None),
    )

    data_source_card = pn.Card(
        pn.FlexBox(
            pn.Column(
                pn.Row(
                    shell.ft_context_select,
                    shell.ft_context_info_hover,
                    sizing_mode="stretch_width",
                    styles={"align-items": "center"},
                ),
                resolved_context_notice,
                shell.ft_context_summary,
                sizing_mode="stretch_width",
                styles={"flex": "1 1 520px"},
            ),
            # Keep the exact same right-side column width as the Self header area
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

    title_card = pn.Card(
        pn.Column(
            pn.Spacer(height=6),
            pn.Row(
                # Left column (width 320) to match rho_card
                pn.Column(
                    pn.Spacer(height=44),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                # Middle column (width 800) for plot
                pn.Column(
                    pn.Spacer(height=10),
                    pn.Column(
                        pn.Column(
                            # Reduced Top Slot
                            pn.Column(
                                pn.Spacer(height=0),
                                sizing_mode="fixed",
                                width=800,
                                height=0,
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
                            # Selector Slot at top: 0px
                            pn.Column(
                                getattr(shell, "ft_view_selector", pn.Spacer(height=0)),
                                sizing_mode="fixed",
                                width=800,
                                height=34,
                                margin=(0, 0, 0, 0),
                                styles={
                                    "position": "absolute",
                                    "top": "0px",
                                    "left": "0px",
                                    "right": "0px",
                                    "z-index": "30",
                                    "pointer-events": "auto",
                                },
                            ),
                            # Plot starts after selector (34px margin)
                            pn.Column(
                                shell.ft_title_plot_pane,
                                sizing_mode="fixed",
                                width=800,
                                height=600,
                                margin=(34, 0, 0, 0),
                                styles={
                                    "overflow": "hidden",
                                    "box-sizing": "border-box",
                                },
                            ),
                            sizing_mode="fixed",
                            width=800,
                            height=634,
                            margin=(0, 0, 0, 0),
                            styles={
                                "position": "relative",
                                "overflow": "visible",
                            },
                        ),
                        sizing_mode="fixed",
                        width=800,
                        styles={"overflow": "hidden"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                ),
                # Right column (width 320)
                pn.Column(
                    pn.Spacer(height=44),
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
                "<h3>Base G(R)</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            pn.pane.HTML(
                "",
                sizing_mode="stretch_width",
                margin=(0, 0, 0, 0),
            ),
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

    rho_card = pn.Card(
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
                    getattr(shell, "ft_rho_run_fit_button", pn.Spacer(height=0)),
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
                # Left column: Table top matches Plot top border
                pn.Column(
                    pn.Spacer(height=0),
                    pn.Column(
                        getattr(shell, "ft_rho_series_selector", pn.Spacer(height=0)),
                        pn.Spacer(height=10),
                        sizing_mode="fixed",
                        width=320,
                        margin=(0, 0, 0, 0),
                        styles={"align-items": "center"},
                    ),
                    getattr(shell, "ft_rho_window_table", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                # Middle column
                pn.Column(
                    pn.Spacer(height=10),
                    pn.Column(
                        pn.Column(
                            # Reduced Top Slot
                            pn.Column(
                                pn.Spacer(height=0),
                                sizing_mode="fixed",
                                width=800,
                                height=0,
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
                            # Selector Slot at top: 0px
                            pn.Column(
                                getattr(shell, "ft_rho_view_selector", pn.Spacer(height=0)),
                                sizing_mode="fixed",
                                width=800,
                                height=34,
                                margin=(0, 0, 0, 0),
                                styles={
                                    "position": "absolute",
                                    "top": "0px",
                                    "left": "0px",
                                    "right": "0px",
                                    "z-index": "30",
                                    "pointer-events": "auto",
                                },
                            ),
                            # Plot starts after selector (34px margin)
                            pn.Column(
                                getattr(shell, "ft_rho_plot_pane", pn.Spacer(height=0)),
                                sizing_mode="fixed",
                                width=800,
                                height=600,
                                margin=(34, 0, 0, 0),
                                styles={
                                    "overflow": "hidden",
                                    "box-sizing": "border-box",
                                },
                            ),
                            sizing_mode="fixed",
                            width=800,
                            height=634,
                            margin=(0, 0, 0, 0),
                            styles={
                                "position": "relative",
                                "overflow": "visible",
                            },
                        ),
                        sizing_mode="fixed",
                        width=800,
                        styles={"overflow": "hidden"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                ),
                # Right column: Table top matches Plot top border
                pn.Column(
                    pn.Spacer(height=60),
                    getattr(shell, "ft_rho_fit_result_table", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            pn.Spacer(height=24),
            # Centered Sliders Row
            pn.Row(
                pn.Row(
                    pn.Spacer(width=320),
                    pn.Column(
                        pn.Row(
                            pn.Spacer(width=100),
                            pn.Column(
                                getattr(shell, "ft_rho_r_filter_controls", pn.Spacer(height=0)),
                                sizing_mode="fixed",
                                width=600,
                                margin=(0, 0, 0, 0),
                                styles={"gap": "0px"},
                            ),
                            pn.Spacer(width=100),
                            sizing_mode="fixed",
                            width=800,
                            margin=(0, 0, 0, 0),
                            styles={"gap": "0px"},
                        ),
                        sizing_mode="fixed",
                        width=800,
                        styles={"align-items": "center"},
                    ),
                    pn.Spacer(width=320),
                    sizing_mode="fixed",
                    width=1440,
                    margin=(14, 0, 0, 0),
                    styles={"margin": "0 auto", "gap": "14px"},
                ),
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Effective Atomic Density</h3>",
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

    real_space_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=320,
                    height=48,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    getattr(shell, "ft_rho_resolve_density_button", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    height=48,
                    styles={"align-items": "center", "justify-content": "center"},
                ),
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=320,
                    height=48,
                    styles={"justify-content": "flex-end", "align-items": "center"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "center", "gap": "14px"},
            ),
            pn.Spacer(height=12),
            pn.Row(
                pn.layout.HSpacer(),
                getattr(shell, "ft_rho_confirm_selection_panel", pn.Spacer(height=0)),
                pn.layout.HSpacer(),
                sizing_mode="stretch_width",
            ),
            pn.Spacer(height=12),
            pn.Row(
                pn.layout.HSpacer(),
                getattr(shell, "ft_real_space_block_view_label", pn.Spacer(height=0)),
                pn.layout.HSpacer(),
                sizing_mode="stretch_width",
                styles={"align-items": "center"},
                margin=(0, 0, 0, 0),
            ),
            pn.Row(
                pn.layout.HSpacer(),
                pn.Row(
                    getattr(shell, "ft_real_space_prev_block_button", pn.Spacer(height=0)),
                    getattr(shell, "ft_real_space_next_block_button", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    margin=(0, 0, 0, 0),
                    styles={"justify-content": "center", "gap": "12px"},
                ),
                pn.layout.HSpacer(),
                sizing_mode="stretch_width",
                styles={"align-items": "center"},
                margin=(0, 0, 2, 0),
            ),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                ),
                pn.Column(
                    getattr(shell, "ft_real_space_plot_pane", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    height=600,
                    margin=(0, 0, 0, 0),
                    styles={
                        "overflow": "hidden",
                        "box-sizing": "border-box",
                    },
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "12px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            pn.Row(
                pn.layout.HSpacer(),
                getattr(shell, "ft_real_space_plot_view_label", pn.Spacer(height=0)),
                pn.layout.HSpacer(),
                sizing_mode="stretch_width",
                styles={"align-items": "center"},
                margin=(2, 0, 0, 0),
            ),
            pn.Spacer(height=10),
            pn.Row(
                pn.layout.HSpacer(),
                pn.Row(
                    getattr(shell, "ft_real_space_prev_plot_button", pn.Spacer(height=0)),
                    getattr(shell, "ft_real_space_next_plot_button", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=800,
                    margin=(0, 0, 0, 0),
                    styles={"justify-content": "center", "gap": "12px"},
                ),
                pn.layout.HSpacer(),
                sizing_mode="stretch_width",
                styles={"align-items": "center"},
                margin=(0, 0, 0, 0),
            ),
            pn.Spacer(height=12),
            sizing_mode="stretch_width",
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Real Space Functions</h3>",
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

    return pn.Column(
        data_source_card,
        pn.Spacer(height=18),
        title_card,
        pn.Spacer(height=18),
        rho_card,
        pn.Spacer(height=18),
        real_space_card,
        pn.Spacer(height=16),
        getattr(shell, "ft_export_card", pn.Spacer(height=0)),
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
