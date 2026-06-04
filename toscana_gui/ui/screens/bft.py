from __future__ import annotations

import panel as pn


def build_bft_section(shell) -> pn.Column:
    if shell.current_project_state is None:
        return pn.Column(
            pn.pane.Markdown(
                "Create or open a project first to configure Back Fourier Transform (BFT).",
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )

    # NOTE: Avoid mutating widget values during render; refresh only the dropdown options/summary.
    if hasattr(shell, "_refresh_bft_context_options"):
        shell._refresh_bft_context_options(apply_selection=False)
    if hasattr(shell, "_refresh_bft_context_summary"):
        shell._refresh_bft_context_summary()
    if hasattr(shell, "_refresh_bft_results_panel"):
        shell._refresh_bft_results_panel()

    resolved_context_notice = _maybe_toast_only(
        shell,
        key="bft:resolved_context_message",
        pane=getattr(shell, "bft_context_message", None),
    )

    data_source_card = pn.Card(
        pn.FlexBox(
            pn.Column(
                pn.Row(
                    shell.bft_context_select,
                    shell.bft_context_info_hover,
                    sizing_mode="stretch_width",
                    styles={"align-items": "center"},
                ),
                resolved_context_notice,
                shell.bft_context_summary,
                sizing_mode="stretch_width",
                styles={"flex": "1 1 520px"},
            ),
            # Keep the exact same right-side column width as the FT header area
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

    back_ft_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Column(
                    shell.bft_iterations_input,
                    getattr(shell, "bft_run_status", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "8px"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    shell.bft_run_button,
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=800,
                    height=48,
                    styles={"align-items": "center"},
                ),
                pn.Column(
                    getattr(shell, "bft_iterations_warning_card", pn.Spacer(height=0)),
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "10px"},
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            pn.Spacer(height=12),
            # Results content (formerly its own "Back-FT Results" card). Keep the
            # same inner grid/positions, but under the Back Fourier Transform header.
            pn.Spacer(height=18),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                ),
                pn.Column(
                    pn.pane.HTML("<h4>Iteration Animation</h4>", margin=(0, 0, 6, 0)),
                    shell.bft_animation_counter,
                    shell.bft_animation_player,
                    shell.bft_animation_pane,
                    sizing_mode="fixed",
                    width=800,
                    styles={"overflow": "visible"},
                ),
                pn.Column(
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            pn.Spacer(height=18),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                ),
                pn.Column(
                    pn.pane.HTML("<h4>Final Functions</h4>", margin=(0, 0, 6, 0)),
                    pn.Row(
                        pn.layout.HSpacer(),
                        shell.bft_final_plot_view_label,
                        pn.layout.HSpacer(),
                        sizing_mode="stretch_width",
                        styles={"align-items": "center"},
                        margin=(0, 0, 0, 0),
                    ),
                    shell.bft_final_plot_pane,
                    pn.Spacer(height=10),
                    pn.Row(
                        pn.layout.HSpacer(),
                        shell.bft_final_prev_plot_button,
                        shell.bft_final_next_plot_button,
                        pn.layout.HSpacer(),
                        sizing_mode="stretch_width",
                        styles={"justify-content": "center", "gap": "12px"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                    styles={"overflow": "visible"},
                ),
                pn.Column(
                    pn.Spacer(height=0),
                    sizing_mode="fixed",
                    width=320,
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            pn.Spacer(height=22),
            sizing_mode="stretch_width",
        ),
        header=pn.Row(
            pn.pane.HTML(
                "<h3>Back Fourier Transform</h3>",
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
        back_ft_card,
        sizing_mode="stretch_width",
    )


def _maybe_toast_only(shell, *, key: str, pane: object) -> object:
    if pane is None:
        return pn.Spacer(height=0)
    message = str(getattr(pane, "object", "") or "").strip()
    if not message:
        return pn.Spacer(height=0)
    alert_type = str(getattr(pane, "alert_type", "secondary") or "secondary")
    if alert_type == "danger":
        try:
            pane.visible = True
        except Exception:
            pass
        if hasattr(shell, "_show_toast_once"):
            shell._show_toast_once(key, level="error", message=message, persistent=True)
        return pane

    # Everything else becomes a toast; keep the inline card clean (matches FT behavior).
    if hasattr(shell, "_show_toast_once"):
        level_map = {
            "primary": "info",
            "secondary": "info",
            "success": "success",
            "warning": "warning",
        }
        shell._show_toast_once(key, level=level_map.get(alert_type, "info"), message=message, persistent=False)
    return pn.Spacer(height=0)
