from __future__ import annotations

import panel as pn


def build_project_section(shell) -> pn.Column:
    return pn.Column(
        pn.Card(
            pn.pane.Markdown(
                "\n".join(
                    [
                        f"**Project name:** {shell.current_project_state.project.name}",
                        f"**Project folder:** `{shell.current_project_root}`",
                        f"**Project file:** `{shell.current_project_file}`",
                        f"**Restored top-level tab:** `{shell.current_top_level_tab}`",
                    ]
                ),
                sizing_mode="stretch_width",
            ),
            title="Project Summary",
            sizing_mode="stretch_width",
        ),
        pn.Card(
            shell.project_editor_name_input,
            pn.Row(shell.save_project_button),
            shell.project_editor_message,
            title="Project Editor",
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
    )
