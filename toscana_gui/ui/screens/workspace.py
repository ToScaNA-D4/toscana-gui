from __future__ import annotations

import panel as pn

from toscana_gui.projects.tasks import WORKSPACE_TAB_TITLES
from toscana_gui.ui.screens.help import build_help_section
from toscana_gui.ui.screens.background import build_background_section
from toscana_gui.ui.screens.numors import build_numors_section
from toscana_gui.ui.screens.normalization import build_normalization_section
from toscana_gui.ui.screens.self_scattering import build_self_scattering_section
from toscana_gui.ui.screens.ft import build_ft_section
from toscana_gui.ui.screens.bft import build_bft_section
from toscana_gui.ui.screens.project import build_project_section
from toscana_gui.ui.screens.run_history import build_run_history_section


def build_workspace_page_body(shell) -> list[object]:
    if shell.workspace_entrypoint == "Start New Project":
        return build_start_project_layout(shell)
    if shell.workspace_entrypoint == "Continue Previous Project":
        return build_continue_project_layout(shell)
    return build_workspace_placeholder_layout()


def build_start_project_layout(shell) -> list[object]:
    if shell.workspace_result != "created" or shell.current_project_state is None:
        shell._show_toast_once(
            "start_project:intro",
            level="info",
            message=(
                "Define the basic project information below. The target folder may be created "
                "if it does not exist yet. If it already exists, it must be empty."
            ),
            persistent=False,
        )
        folder_widget = (
            shell.project_folder_input
            if shell.project_folder_mode.value == "Enter folder path"
            else pn.Column(
                shell.project_folder_selected_display,
                pn.Row(
                    shell.project_folder_browse_button,
                    shell.project_folder_native_browse_button,
                ),
                (
                    pn.Card(
                        shell.project_folder_file_selector,
                        pn.Row(
                            shell.project_folder_confirm_button,
                            shell.project_folder_cancel_button,
                        ),
                        title="Choose Project Folder",
                        sizing_mode="stretch_width",
                    )
                    if shell.project_folder_browser_visible
                    else pn.Spacer(height=0)
                ),
                sizing_mode="stretch_width",
            )
        )
        return [
            pn.Card(
                shell.project_name_input,
                shell.project_folder_mode,
                folder_widget,
                pn.Row(shell.create_project_confirm_button),
                _maybe_inline_or_toast(
                    shell,
                    key="start_project:message",
                    pane=shell.start_project_message,
                ),
                title="Start New Project",
                sizing_mode="stretch_width",
            ),
        ]

    return build_loaded_project_layout(shell)


def build_continue_project_layout(shell) -> list[object]:
    if shell.workspace_result == "opened" and shell.current_project_state is not None:
        return build_loaded_project_layout(shell)

    shell._show_toast_once(
        "continue_project:intro",
        level="info",
        message=(
            "Continue a previous session by choosing a recent project or opening an "
            "`toscana-project.json` file directly."
        ),
        persistent=False,
    )
    shell._refresh_recent_projects_view()
    manual_selected = (
        bool(shell.manual_project_file_input.value.strip())
        or bool(shell.manual_project_file_selected_display.value.strip())
        or shell.manual_project_file_browser_visible
    )
    active_card_styles = {
        "border": "2px solid #0B6FA4",
        "box-shadow": "0 10px 26px rgba(0, 0, 0, 0.10)",
    }
    inactive_card_styles = {
        "border": "1px solid rgba(0, 0, 0, 0.08)",
    }
    manual_file_widget = (
        shell.manual_project_file_input
        if shell.manual_project_file_mode.value == "Enter file path"
        else pn.Column(
            shell.manual_project_file_selected_display,
            pn.Row(
                shell.manual_project_file_browse_button,
                shell.manual_project_file_native_browse_button,
            ),
            (
                pn.Card(
                    shell.manual_project_file_selector,
                    pn.Row(
                        shell.manual_project_file_confirm_button,
                        shell.manual_project_file_cancel_button,
                    ),
                    title="Choose Project File",
                    sizing_mode="stretch_width",
                )
                if shell.manual_project_file_browser_visible
                else pn.Spacer(height=0)
            ),
            sizing_mode="stretch_width",
        )
    )
    return [
        pn.FlexBox(
            pn.Card(
                shell.recent_projects_column,
                title="Recent Projects",
                sizing_mode="stretch_width",
                min_width=420,
                styles={
                    "flex": "1 1 520px",
                    **(inactive_card_styles if manual_selected else active_card_styles),
                },
            ),
            pn.Card(
                shell.manual_project_file_mode,
                manual_file_widget,
                pn.Row(shell.manual_open_button),
                _maybe_inline_or_toast(
                    shell,
                    key="continue_project:message",
                    pane=shell.continue_project_message,
                ),
                title="Open Project File",
                sizing_mode="stretch_width",
                min_width=420,
                styles={
                    "flex": "1 1 520px",
                    **(active_card_styles if manual_selected else inactive_card_styles),
                },
            ),
            gap="18px",
            flex_wrap="wrap",
            sizing_mode="stretch_width",
        ),
    ]


def build_loaded_project_layout(shell) -> list[object]:
    contents: list[object] = [build_workspace_navigation(shell)]
    if shell.reset_project_prompt.visible:
        contents.append(
            pn.Card(
                shell.reset_project_prompt,
                pn.Row(
                    shell.reset_project_confirm_button,
                    shell.reset_project_cancel_button,
                    sizing_mode="stretch_width",
                ),
                title="Reset Project",
                sizing_mode="stretch_width",
            )
        )
    if shell.workspace_message.visible:
        contents.append(shell.workspace_message)
    contents.append(build_workspace_section_content(shell, shell.current_top_level_tab))
    return contents


def build_workspace_navigation(shell) -> pn.FlexBox:
    return pn.FlexBox(
        shell.back_to_menu_button,
        *[shell.workspace_buttons[tab_name] for tab_name in shell.workspace_buttons],
        gap="10px",
        flex_wrap="wrap",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )


def build_workspace_section_content(shell, tab_name: str) -> object:
    if tab_name == "project":
        return build_project_section(shell)
    if tab_name == "numors":
        return build_numors_section(shell)
    if tab_name == "background":
        return build_background_section(shell)
    if tab_name == "normalization":
        return build_normalization_section(shell)
    if tab_name == "self":
        return build_self_scattering_section(shell)
    if tab_name == "ft":
        return build_ft_section(shell)
    if tab_name == "bft":
        return build_bft_section(shell)
    if tab_name == "run_history":
        return build_run_history_section(shell)
    return build_help_section()


def build_placeholder_section(tab_name: str) -> pn.Column:
    return pn.Column(
        pn.pane.Markdown(
            f"{WORKSPACE_TAB_TITLES[tab_name]} content will be added in a later slice.",
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
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


def build_workspace_placeholder_layout() -> list[object]:
    return [
        pn.pane.Alert(
            "This workspace shell is intentionally minimal. "
            "Project loading flows will be implemented in later slices.",
            alert_type="primary",
            sizing_mode="stretch_width",
        ),
        pn.Row(
            pn.Card(
                pn.pane.Markdown("Project area placeholder"),
                title="Project",
                sizing_mode="stretch_width",
            ),
            pn.Card(
                pn.pane.Markdown("Workflow area placeholder"),
                title="Workspace Content",
                sizing_mode="stretch_width",
            ),
        ),
    ]


def build_workspace_page(shell) -> pn.Column:
    return pn.Column(
        *[
            pn.pane.Markdown(
                "# Workspace",
                sizing_mode="stretch_width",
            ),
            pn.pane.Markdown(
                f"**Entered from:** {shell.workspace_entrypoint}",
                sizing_mode="stretch_width",
            ),
        ],
        *build_workspace_page_body(shell),
        sizing_mode="stretch_both",
    )
