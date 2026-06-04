from __future__ import annotations

import panel as pn

from toscana_gui.ui.theme import APP_TITLE, LOGO_PATH


def build_landing_page(shell) -> pn.Column:
    logo_pane = pn.pane.PNG(
        LOGO_PATH,
        width=280,
        sizing_mode="fixed",
        margin=(0, 0, 0, 0),
    )

    center_column = pn.Column(
        pn.Column(
            logo_pane,
            width=280,
            align="center",
            styles={"margin": "0 auto"},
        ),
        pn.Spacer(height=12),
        pn.pane.HTML(
            f"""
            <div style="text-align: center; width: 100%;">
              <h1 style="
                margin: 0;
                font-size: 2.4rem;
                letter-spacing: 0.03em;
                font-family: 'IBM Plex Sans', sans-serif;
              ">{APP_TITLE}</h1>
            </div>
            """,
            sizing_mode="stretch_width",
        ),
        pn.Spacer(height=8),
        pn.pane.Markdown(
            "Choose how you want to begin your ToScaNA session.",
            sizing_mode="stretch_width",
            styles={
                "text-align": "center",
                "font-family": "'IBM Plex Sans', sans-serif",
            },
        ),
        pn.Spacer(height=22),
        build_pending_navigation_prompt(shell),
        pn.Spacer(height=14),
        pn.Column(
            shell.start_project_button,
            shell.continue_project_button,
            shell.help_button,
            width=360,
            align="center",
            styles={"margin": "0 auto"},
        ),
        sizing_mode="stretch_width",
        styles={
            "max-width": "760px",
            "margin": "0 auto",
        },
    )
    return pn.Column(
        pn.Spacer(height=28),
        center_column,
        sizing_mode="stretch_both",
    )


def build_pending_navigation_prompt(shell) -> object:
    if shell.pending_navigation_action is None:
        return pn.Spacer(height=0)
    return pn.Card(
        pn.pane.Markdown(
            "You have unsaved changes in the currently loaded project. "
            "Choose how to proceed before switching projects.",
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.save_and_continue_button,
            shell.discard_and_continue_button,
            shell.cancel_navigation_button,
        ),
        title="Unsaved Changes",
        sizing_mode="stretch_width",
    )
