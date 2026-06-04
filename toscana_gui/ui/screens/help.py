from __future__ import annotations

import panel as pn


def build_help_section() -> pn.Column:
    return pn.Column(
        pn.pane.Markdown(
            "Help and About content will be added in a later slice.",
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )
