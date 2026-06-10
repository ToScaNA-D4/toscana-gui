from __future__ import annotations

from pathlib import Path

import panel as pn

from toscana_gui.background.tasks import BACKGROUND_SOURCE_OPTIONS
from toscana_gui.background.tasks import BACKGROUND_SUBTRACTION_METHOD_OPTIONS
from toscana_gui.numors.tasks import NUMORS_SOURCE_OPTIONS
from toscana_gui.normalization.tasks import QSPDATA_DIR
from toscana_gui.paths import REPO_ROOT
from toscana_gui.projects.tasks import WorkspaceTab
from toscana_gui.ui.custom_sliders import ToscanaRangeSlider
from toscana_gui.ui.run_block_viewer import create_run_block_plot_display


def initialize_shell_widgets(shell) -> None:
    shell.content = pn.Column(sizing_mode="stretch_both")
    shell.toast_duration_ms = 8000
    shell.toast_success_duration_ms  = 5000
    shell.toast_info_duration_ms = 6000
    shell.reset_project_button = pn.widgets.Button(
        name="🗑",
        button_type="light",
        width=48,
        height=44,
    )
    shell.reset_project_prompt = pn.pane.Alert(
        "",
        alert_type="danger",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.reset_project_confirm_button = pn.widgets.Button(
        name="Yes, reset project",
        button_type="danger",
        sizing_mode="fixed",
        width=200,
        height=44,
    )
    shell.reset_project_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
    )

    shell.start_project_button = pn.widgets.Button(
        name="Start New Project",
        button_type="primary",
        sizing_mode="fixed",
        width=360,
        height=60,
    )
    shell.continue_project_button = pn.widgets.Button(
        name="Continue Previous Project",
        button_type="default",
        sizing_mode="fixed",
        width=360,
        height=60,
    )
    shell.help_button = pn.widgets.Button(
        name="Help (Coming soon)",
        button_type="light",
        disabled=True,
        sizing_mode="fixed",
        width=360,
        height=60,
    )
    shell.back_to_menu_button = pn.widgets.Button(
        name="Back to Main Menu",
        button_type="default",
        sizing_mode="fixed",
        width=180,
    )
    shell.workspace_buttons: dict[WorkspaceTab, pn.widgets.Button] = {
        tab_name: pn.widgets.Button(
            name=title,
            button_type="light",
            sizing_mode="fixed",
            width=150,
        )
        for tab_name, title in (
            ("project", "Project"),
            ("numors", "Numors"),
            ("background", "Background"),
            ("normalization", "Normalization"),
            ("self", "Self"),
            ("ft", "FT"),
            ("bft", "BFT"),
            ("run_history", "Run History"),
            ("help", "Help / About"),
        )
    }
    shell.project_name_input = pn.widgets.TextInput(
        name="Project Name",
        placeholder="My D4 Session",
        sizing_mode="stretch_width",
    )
    projects_root = REPO_ROOT / "Projects"
    shell.project_folder_input = pn.widgets.TextInput(
        name="Project Folder",
        placeholder=str(projects_root / "My-D4-Session"),
        sizing_mode="stretch_width",
    )
    shell.project_folder_input.value = str(projects_root)
    shell._project_folder_autofill_enabled = True
    shell._project_folder_autofill_programmatic = False
    shell._project_folder_autofill_last_value = str(projects_root)
    shell.project_folder_mode = pn.widgets.RadioBoxGroup(
        name="Project Folder Input",
        options=["Enter folder path", "Choose folder"],
        value="Enter folder path",
        inline=True,
        sizing_mode="stretch_width",
    )
    shell.project_folder_browser_visible = False
    shell._project_folder_candidate: Path | None = None
    shell.project_folder_selected_display = pn.widgets.TextInput(
        name="Selected Folder",
        placeholder="No folder selected yet.",
        disabled=True,
        sizing_mode="stretch_width",
    )
    shell.project_folder_browse_button = pn.widgets.Button(
        name="Choose Folder...",
        button_type="primary",
        sizing_mode="fixed",
        width=200,
        height=44,
        disabled=False,
    )
    shell.project_folder_native_browse_button = pn.widgets.Button(
        name="Choose Folder (Windows)...",
        button_type="light",
        sizing_mode="fixed",
        width=240,
        height=44,
    )
    shell.project_folder_confirm_button = pn.widgets.Button(
        name="Use Selected Folder",
        button_type="primary",
        sizing_mode="fixed",
        width=220,
        height=44,
        disabled=True,
    )
    shell.project_folder_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
    )
    shell.project_folder_file_selector = pn.widgets.FileSelector(
        directory=str(shell._default_project_folder_browser_root()),
        only_files=False,
        size=8,
        sizing_mode="stretch_width",
    )
    shell.create_project_confirm_button = pn.widgets.Button(
        name="Open or Create Project",
        button_type="primary",
        sizing_mode="fixed",
        width=220,
        height=52,
    )
    shell.start_project_message = pn.pane.Alert(
        "This branch uses a fixed project root and derives the project name automatically.",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.project_editor_name_input = pn.widgets.TextInput(
        name="Project Name",
        disabled=True,
        sizing_mode="stretch_width",
    )
    shell.save_project_button = pn.widgets.Button(
        name="Save Project",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
    )
    shell.project_editor_message = pn.pane.Alert(
        "No unsaved changes.",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.manual_project_file_input = pn.widgets.TextInput(
        name="Project File",
        placeholder=r"D:\ILL\ToScaNA\Projects\my-session\toscana-project.json",
        sizing_mode="stretch_width",
    )
    shell.manual_project_file_mode = pn.widgets.RadioBoxGroup(
        name="Open Project Input",
        options=["Enter file path", "Choose file"],
        value="Enter file path",
        inline=True,
        sizing_mode="stretch_width",
    )
    shell.manual_project_file_browser_visible = False
    shell._manual_project_file_candidate: Path | None = None
    shell.manual_project_file_selected_display = pn.widgets.TextInput(
        name="Selected File",
        placeholder="No file selected yet.",
        disabled=True,
        sizing_mode="stretch_width",
    )
    shell.manual_project_file_browse_button = pn.widgets.Button(
        name="Choose File...",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=44,
    )
    shell.manual_project_file_native_browse_button = pn.widgets.Button(
        name="Choose File (Windows)...",
        button_type="light",
        sizing_mode="fixed",
        width=220,
        height=44,
    )
    shell.manual_project_file_confirm_button = pn.widgets.Button(
        name="Use Selected File",
        button_type="primary",
        sizing_mode="fixed",
        width=200,
        height=44,
        disabled=True,
    )
    shell.manual_project_file_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
    )
    shell.manual_project_file_selector = pn.widgets.FileSelector(
        directory=str(REPO_ROOT),
        file_pattern="toscana-project.json",
        only_files=True,
        size=8,
        sizing_mode="stretch_width",
    )
    shell.manual_open_button = pn.widgets.Button(
        name="Open Project File",
        button_type="primary",
        sizing_mode="fixed",
        width=220,
        height=52,
    )
    shell.continue_project_message = pn.pane.Alert(
        "Choose a recent project or open an `toscana-project.json` file manually.",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.workspace_message = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.numors_source_mode = pn.widgets.RadioBoxGroup(
        name="Input Mode",
        inline=False,
        options=list(NUMORS_SOURCE_OPTIONS),
        value=NUMORS_SOURCE_OPTIONS[0],
        sizing_mode="stretch_width",
    )
    shell.numors_par_dropdown = pn.widgets.Select(
        name="Numors `.par`",
        options={"Open a project first.": ""},
        value="",
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
    )
    shell.numors_manual_path_input = pn.widgets.TextInput(
        name="File Path",
        placeholder=r"D:\ILL\ToScaNA\Project\parfiles\do_name.par",
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
    )
    shell.numors_source_stack = pn.Column(
        shell.numors_par_dropdown,
        shell.numors_manual_path_input,
        sizing_mode="stretch_width",
    )
    shell.numors_validate_button = pn.widgets.Button(
        name="Validate File",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
    )
    shell.numors_run_button = pn.widgets.Button(
        name="Run d4creg",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.numors_block_select = pn.widgets.Select(
        name="Block",
        options={},
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 20),
    )
    shell.numors_prev_block_button = pn.widgets.Button(
        name="Prev Block",
        icon="chevron-left",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
    )
    shell.numors_next_block_button = pn.widgets.Button(
        name="Next Block",
        icon="chevron-right",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
    )
    shell.numors_prev_plot_button = pn.widgets.Button(
        name="Prev Plot",
        icon="chevron-left",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
    )
    shell.numors_next_plot_button = pn.widgets.Button(
        name="Next Plot",
        icon="chevron-right",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
    )
    shell.numors_block_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(6, 0, 0, 0),
    )
    shell.numors_block_view_label = pn.pane.Markdown(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
    )
    shell.numors_plot_view_label = pn.pane.Markdown(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
    )
    shell.numors_block_plot_display = create_run_block_plot_display(width=800, height=480)
    # Make the run-block viewer more compact by removing default pane margins.
    shell.numors_block_plot_display.message_pane.margin = (0, 0, 0, 0)
    shell.numors_block_plot_display.image_pane.margin = (0, 0, 0, 0)
    shell.numors_block_plot_fixed = pn.Column(
        shell.numors_block_plot_display.message_pane,
        shell.numors_block_plot_display.image_pane,
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
    )
    shell.numors_block_plot_centered = pn.Row(
        pn.layout.HSpacer(),
        shell.numors_block_plot_fixed,
        pn.layout.HSpacer(),
        sizing_mode="stretch_width",
        styles={"align-items": "center"},
    )
    shell.numors_run_blocks_header_left = pn.Column(
        pn.Row(
            shell.numors_block_select,
            shell.numors_block_info_hover,
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
        ),
        sizing_mode="stretch_width",
        styles={"flex": "1 1 520px"},
    )
    shell.numors_run_blocks_header_right = pn.Column(
        pn.Spacer(height=10),
        sizing_mode="stretch_width",
        styles={"flex": "0 1 280px"},
    )
    shell.numors_run_blocks_header = pn.FlexBox(
        shell.numors_run_blocks_header_left,
        shell.numors_run_blocks_header_right,
        gap="18px",
        flex_wrap="wrap",
        sizing_mode="stretch_width",
        margin=(8, 0, 0, 0),
        css_classes=["toscana-normalization-source-header"],
    )
    shell.numors_run_blocks_block_buttons = pn.Row(
        shell.numors_prev_block_button,
        shell.numors_next_block_button,
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"justify-content": "center", "gap": "12px"},
    )
    shell.numors_run_blocks_plot_buttons = pn.Row(
        shell.numors_prev_plot_button,
        shell.numors_next_plot_button,
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"justify-content": "center", "gap": "12px"},
    )
    shell.numors_run_blocks_card = pn.Card(
        shell.numors_run_blocks_header,
        pn.Row(
            pn.layout.HSpacer(),
            shell.numors_block_view_label,
            pn.layout.HSpacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
            margin=(0, 0, 0, 0),
        ),
        pn.Row(
            pn.layout.HSpacer(),
            shell.numors_run_blocks_block_buttons,
            pn.layout.HSpacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
            margin=(0, 0, 2, 0),
        ),
        shell.numors_block_plot_centered,
        pn.Row(
            pn.layout.HSpacer(),
            shell.numors_plot_view_label,
            pn.layout.HSpacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
            margin=(2, 0, 0, 0),
        ),
        pn.Row(
            pn.layout.HSpacer(),
            shell.numors_run_blocks_plot_buttons,
            pn.layout.HSpacer(),
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
            margin=(0, 0, 0, 0),
        ),
        title="Run Blocks",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-overflow-visible"],
    )
    shell.numors_message = pn.pane.Alert(
        "Choose a `.par` file and validate it.",
        alert_type="secondary",
        visible=False,
        sizing_mode="stretch_width",
    )
    shell.numors_validation_info_hover = pn.widgets.TooltipIcon(
        value="",
        visible=False,
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.numors_import_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.numors_import_confirm_button = pn.widgets.Button(
        name="Copy Into Project",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=44,
    )
    shell.numors_import_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
    )
    shell.numors_import_card = pn.Card(
        shell.numors_import_prompt,
        pn.Row(
            shell.numors_import_confirm_button,
            shell.numors_import_cancel_button,
        ),
        title="Import Required",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.background_source_mode = pn.widgets.RadioBoxGroup(
        name="Input Mode",
        inline=False,
        options=list(BACKGROUND_SOURCE_OPTIONS),
        value=BACKGROUND_SOURCE_OPTIONS[0],
        sizing_mode="stretch_width",
    )
    shell.background_par_dropdown = pn.widgets.Select(
        name="Sample `.par`",
        options={"Open a project first.": ""},
        value="",
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
    )
    shell.background_manual_path_input = pn.widgets.TextInput(
        name="File Path",
        placeholder=r"D:\ILL\ToScaNA\Project\parfiles\sample.par",
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
    )
    shell.background_source_stack = pn.Column(
        shell.background_par_dropdown,
        shell.background_manual_path_input,
        sizing_mode="stretch_width",
    )
    shell.background_validate_button = pn.widgets.Button(
        name="Validate File",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
    )
    shell.background_extract_button = pn.widgets.Button(
        name="Extract Sample",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.background_message = pn.pane.Alert(
        "Select a sample .par file to get started.",
        alert_type="secondary",
        visible=False,
        sizing_mode="stretch_width",
    )
    shell.background_validation_info_hover = pn.widgets.TooltipIcon(
        value="",
        visible=False,
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.background_raw_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=1000,
        height=600,
    )
    shell.background_subtraction_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )
    shell.background_no_data_pane = pn.pane.Markdown(
        "No extracted sample data yet. Run **Extract Sample** to generate interactive plots.",
        sizing_mode="stretch_width",
        visible=True,
    )
    shell.background_raw_plot_alert = pn.pane.Alert(
        "",
        alert_type="danger",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_raw_plot_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=220,
                    height=40,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=1000,
                    height=40,
                    styles={"align-items": "center"},
                ),
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=220,
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
                    width=220,
                ),
                pn.Column(
                    shell.background_raw_plot_pane,
                    sizing_mode="fixed",
                    width=1000,
                    styles={"overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    sizing_mode="fixed",
                    width=220,
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
                "<h3>Raw Data</h3>",
                css_classes=["card-title"],
                margin=(5, 0),
            ),
            sizing_mode="stretch_width",
            styles={"align-items": "center", "justify-content": "flex-start", "gap": "12px"},
            css_classes=["toscana-normalization-source-card-header"],
        ),
        sizing_mode="stretch_width",
        visible=False,
        collapsible=False,
        margin=(0, 0, 0, 0),
        css_classes=[
            "toscana-normalization-card",
            "toscana-normalization-card--source-group",
        ],
    )
    shell.background_subtraction_plot_alert = pn.pane.Alert(
        "",
        alert_type="danger",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_subtraction_plot_card = pn.Card(
        shell.background_subtraction_plot_pane,
        title="Direct Sample Subtraction (Sample - Container)",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_import_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_import_confirm_button = pn.widgets.Button(
        name="Copy into Project",
        button_type="primary",
        sizing_mode="fixed",
        width=200,
        height=44,
        disabled=False,
    )
    shell.background_import_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
    )
    shell.background_import_card = pn.Card(
        shell.background_import_prompt,
        pn.Row(
            shell.background_import_confirm_button,
            shell.background_import_cancel_button,
        ),
        title="Import Required",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_subtraction_method = pn.widgets.RadioButtonGroup(
        name="Method",
        options=list(BACKGROUND_SUBTRACTION_METHOD_OPTIONS),
        value=BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
        button_type="primary",
        sizing_mode="stretch_width",
    )
    shell.background_sample_method_select = pn.widgets.Select(
        name="",
        options={
            "Linear Combination": BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
            "Monte Carlo Simulation": BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1],
        },
        value=BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
        sizing_mode="fixed",
        width=440,
    )
    shell.background_sample_method_info_hover = pn.widgets.TooltipIcon(
        value=(
            "<div style=\"max-width: 320px; line-height: 1.4; white-space: normal; "
            "overflow-wrap: anywhere; word-break: break-word;\">"
            "Select Background Subtraction Method"
            "</div>"
        ),
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.background_linear_t_start = pn.widgets.FloatInput(
        name="t start",
        value=-1.0,
        step=0.05,
        sizing_mode="stretch_width",
    )
    shell.background_linear_t_stop = pn.widgets.FloatInput(
        name="t stop",
        value=2.0,
        step=0.05,
        sizing_mode="stretch_width",
    )
    shell.background_linear_t_step = pn.widgets.FloatInput(
        name="t step",
        value=0.05,
        step=0.01,
        start=1e-6,
        sizing_mode="stretch_width",
    )
    shell.background_linear_smoothing = pn.widgets.FloatInput(
        name="Smoothing factor",
        value=0.01,
        step=0.005,
        start=0.0,
        end=1.0,
        sizing_mode="stretch_width",
    )
    shell.background_linear_ignore_points = pn.widgets.IntInput(
        name="Ignore first N points",
        value=25,
        step=1,
        start=0,
        sizing_mode="stretch_width",
    )
    shell.background_sample_use_custom_t_toggle = pn.widgets.Checkbox(
        name="Use Custom t",
        value=False,
        sizing_mode="stretch_width",
    )
    shell.background_sample_custom_t_input = pn.widgets.FloatInput(
        name="Custom t",
        value=0.8,
        step=0.01,
        sizing_mode="stretch_width",
    )
    shell.background_linear_t_mode = pn.widgets.RadioButtonGroup(
        name="t selection",
        options=["Use computed t", "Use custom t"],
        value="Use computed t",
        button_type="default",
        sizing_mode="stretch_width",
    )
    shell.background_linear_custom_t = pn.widgets.FloatInput(
        name="Custom t",
        value=0.8,
        step=0.01,
        sizing_mode="stretch_width",
    )
    shell.background_linear_compute_button = pn.widgets.Button(
        name="Compute Linear Combination",
        button_type="primary",
        sizing_mode="fixed",
        width=260,
        height=48,
        disabled=False,
    )
    shell.background_sample_use_computed_t_button = pn.widgets.Button(
        name="Use Computed t",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=44,
        disabled=True,
    )
    shell.background_sample_use_custom_t_button = pn.widgets.Button(
        name="Use Custom t",
        button_type="light",
        sizing_mode="fixed",
        width=180,
        height=44,
        disabled=True,
    )
    shell.background_sample_summary_table = pn.pane.HTML(
        (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Summary</div>"
            "<div class=\"toscana-fit-result-table__meta\">t source: <strong>—</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">t value: <strong>—</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">Sample: <strong>—</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">Computed settings: <strong>—</strong></div>"
            "</div>"
        ),
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )
    shell.background_sample_monte_carlo_placeholder_pane = pn.pane.Markdown(
        "Monte Carlo Simulation will be implemented in a future iteration.",
        sizing_mode="fixed",
        width=800,
        height=600,
        margin=(0, 0, 0, 0),
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "text-align": "center",
        },
        visible=False,
    )
    shell.background_sample_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=[
            """
            input[type="checkbox"] {
              appearance: none;
              -webkit-appearance: none;
              width: 52px;
              height: 28px;
              border-radius: 999px;
              background: rgba(148, 163, 184, 0.35);
              border: 1px solid rgba(148, 163, 184, 0.55);
              position: relative;
              cursor: pointer;
              transition: background 180ms ease, border-color 180ms ease;
              box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
            }

            input[type="checkbox"]::before {
              content: "";
              position: absolute;
              top: 3px;
              left: 3px;
              width: 22px;
              height: 22px;
              border-radius: 999px;
              background: rgba(255, 255, 255, 0.92);
              box-shadow: 0 6px 16px rgba(15, 23, 42, 0.18);
              transition: transform 180ms cubic-bezier(0.2, 0.7, 0.2, 1);
            }

            input[type="checkbox"]:checked {
              background: rgba(37, 99, 235, 0.26);
              border-color: rgba(37, 99, 235, 0.42);
            }

            input[type="checkbox"]:checked::before {
              transform: translateX(24px);
            }

            input[type="checkbox"]:focus-visible {
              outline: none;
              box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.28);
            }
            """
        ],
    )
    shell.background_sample_view_selector = pn.Row(
        pn.pane.Markdown(
            "Switch View",
            margin=(0, 10, 0, 0),
            align="center",
            styles={
                "font-size": "0.86rem",
                "font-weight": "700",
                "color": "rgba(15, 23, 42, 0.82)",
            },
        ),
        pn.Column(
            shell.background_sample_view_switch,
            margin=(45, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-end",
        },
    )
    shell.background_linear_message = pn.pane.Alert(
        "Compute a linear-combination background model to estimate the best t parameter.",
        alert_type="secondary",
        visible=False,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_t_start = pn.widgets.FloatInput(
        name="t start",
        value=-1.0,
        step=0.05,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_t_stop = pn.widgets.FloatInput(
        name="t stop",
        value=2.0,
        step=0.05,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_t_step = pn.widgets.FloatInput(
        name="t step",
        value=0.05,
        step=0.01,
        start=1e-6,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_smoothing = pn.widgets.FloatInput(
        name="Smoothing factor",
        value=0.01,
        step=0.005,
        start=0.0,
        end=1.0,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_ignore_points = pn.widgets.IntInput(
        name="Ignore first N points",
        value=25,
        step=1,
        start=0,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_method_select = pn.widgets.Select(
        name="",
        options={
            "Linear Combination": BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
            "Monte Carlo Simulation": BACKGROUND_SUBTRACTION_METHOD_OPTIONS[1],
        },
        value=BACKGROUND_SUBTRACTION_METHOD_OPTIONS[0],
        sizing_mode="fixed",
        width=440,
    )
    shell.background_vanadium_method_info_hover = pn.widgets.TooltipIcon(
        value=(
            "<div style=\"max-width: 320px; line-height: 1.4; white-space: normal; "
            "overflow-wrap: anywhere; word-break: break-word;\">"
            "Select Vanadium Background Subtraction Method"
            "</div>"
        ),
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.background_vanadium_use_custom_t_toggle = pn.widgets.Checkbox(
        name="Use Custom t",
        value=False,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_custom_t_input = pn.widgets.FloatInput(
        name="Custom t",
        value=0.8,
        step=0.01,
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_use_computed_t_button = pn.widgets.Button(
        name="Use Computed t",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=44,
        disabled=True,
    )
    shell.background_vanadium_use_custom_t_button = pn.widgets.Button(
        name="Use Custom t",
        button_type="light",
        sizing_mode="fixed",
        width=180,
        height=44,
        disabled=True,
    )
    shell.background_vanadium_summary_table = pn.pane.HTML(
        (
            "<div class=\"toscana-fit-window-table\">"
            "<div class=\"toscana-fit-result-table__title\">Summary</div>"
            "<div class=\"toscana-fit-result-table__meta\">View: <strong>&mdash;</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">t source: <strong>&mdash;</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">t value: <strong>&mdash;</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">Sample: <strong>&mdash;</strong></div>"
            "<div class=\"toscana-fit-result-table__meta\">Computed settings: <strong>&mdash;</strong></div>"
            "</div>"
        ),
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )
    shell.background_vanadium_direct_placeholder_pane = pn.pane.Markdown(
        "Direct Subtraction for vanadium will be implemented in a future iteration.",
        sizing_mode="fixed",
        width=800,
        height=600,
        margin=(0, 0, 0, 0),
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "text-align": "center",
        },
        visible=False,
    )
    shell.background_vanadium_monte_carlo_placeholder_pane = pn.pane.Markdown(
        "Monte Carlo Simulation for vanadium will be implemented in a future iteration.",
        sizing_mode="fixed",
        width=800,
        height=600,
        margin=(0, 0, 0, 0),
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
            "text-align": "center",
        },
        visible=False,
    )
    shell.background_vanadium_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=shell.background_sample_view_switch.stylesheets
        if hasattr(shell, "background_sample_view_switch")
        else [],
    )
    shell.background_vanadium_view_selector = pn.Row(
        pn.pane.Markdown(
            "Switch View",
            margin=(0, 10, 0, 0),
            align="center",
            styles={
                "font-size": "0.86rem",
                "font-weight": "700",
                "color": "rgba(15, 23, 42, 0.82)",
            },
        ),
        pn.Column(
            shell.background_vanadium_view_switch,
            margin=(45, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-end",
        },
    )
    shell.background_vanadium_t_mode = pn.widgets.RadioButtonGroup(
        name="t selection",
        options=["Use computed t", "Use custom t"],
        value="Use computed t",
        button_type="default",
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_custom_t = pn.widgets.FloatInput(
        name="Custom t",
        value=0.8,
        step=0.01,
        sizing_mode="stretch_width",
        disabled=True,
    )
    shell.background_vanadium_compute_button = pn.widgets.Button(
        name="Compute Linear Combination",
        button_type="primary",
        sizing_mode="fixed",
        width=260,
        height=48,
        disabled=False,
    )
    shell.background_vanadium_message = pn.pane.Alert(
        "Compute a vanadium background model to estimate the best t parameter.",
        visible=False,
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.background_vanadium_controls_card = pn.Card(
        pn.Row(
            shell.background_vanadium_t_start,
            shell.background_vanadium_t_stop,
            shell.background_vanadium_t_step,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_vanadium_smoothing,
            shell.background_vanadium_ignore_points,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_vanadium_compute_button,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_vanadium_t_mode,
            shell.background_vanadium_custom_t,
            sizing_mode="stretch_width",
        ),
        shell.background_vanadium_message,
        title="Normalization (Vanadium)",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.background_vanadium_chi_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )
    shell.background_vanadium_subtraction_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
        visible=False,
    )
    shell.background_final_signals_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=1000,
        height=600,
    )
    shell.background_final_signals_plot_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=220,
                    height=40,
                    styles={"justify-content": "flex-start", "align-items": "center"},
                ),
                pn.Row(
                    pn.layout.HSpacer(),
                    sizing_mode="fixed",
                    width=1000,
                    height=40,
                    styles={"align-items": "center"},
                ),
                pn.Row(
                    pn.Spacer(width=0),
                    sizing_mode="fixed",
                    width=220,
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
                    width=220,
                ),
                pn.Column(
                    shell.background_final_signals_plot_pane,
                    sizing_mode="fixed",
                    width=1000,
                    styles={"overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=44),
                    sizing_mode="fixed",
                    width=220,
                ),
                sizing_mode="fixed",
                width=1440,
                styles={"margin": "0 auto", "align-items": "flex-start", "gap": "14px"},
            ),
            sizing_mode="fixed",
            width=1440,
            styles={"margin": "0 auto"},
        ),
        title="Final Background Subtracted Signals",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.background_export_folder_input = pn.widgets.TextInput(
        name="Export folder",
        value="qspdata",
        placeholder="qspdata",
        sizing_mode="stretch_width",
    )
    shell.background_export_button = pn.widgets.Button(
        name="Export Data",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.background_export_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.background_export_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_export_confirm_button = pn.widgets.Button(
        name="Proceed",
        button_type="danger",
        sizing_mode="fixed",
        width=140,
        height=44,
        disabled=False,
    )
    shell.background_export_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
        disabled=False,
    )
    shell.background_export_prompt_card = pn.Card(
        shell.background_export_prompt,
        pn.Row(
            shell.background_export_confirm_button,
            shell.background_export_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Confirm Export",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )
    shell.background_export_card = pn.Card(
        pn.Column(
            shell.background_export_folder_input,
            pn.Row(
                shell.background_export_button,
                shell.background_export_info_hover,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        shell.background_export_prompt_card,
        title="Export Data",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
        styles={"overflow": "visible", "margin-bottom": "180px"},
        visible=True,
    )
    shell.background_linear_chi_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )
    shell.background_linear_subtraction_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
        visible=False,
    )
    shell.background_subtraction_sample_card = pn.Card(
        pn.Column(
            pn.pane.HTML(
                '<div id="toscana-bg-method-anchor"></div>',
                margin=(0, 0, 0, 0),
            ),
            pn.Spacer(height=12),
            pn.Row(
                pn.Spacer(width=320),
                pn.Column(
                    pn.Row(
                        pn.layout.HSpacer(),
                        pn.Row(
                            shell.background_sample_method_select,
                            shell.background_sample_method_info_hover,
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
            pn.Spacer(height=16),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=96),
                    pn.Row(
                        shell.background_linear_t_start,
                        shell.background_linear_t_stop,
                        shell.background_linear_t_step,
                        sizing_mode="stretch_width",
                    ),
                    pn.Spacer(height=12),
                    shell.background_linear_smoothing,
                    pn.Spacer(height=12),
                    shell.background_linear_ignore_points,
                    pn.Spacer(height=12),
                    shell.background_sample_use_custom_t_toggle,
                    pn.Spacer(height=10),
                    shell.background_sample_custom_t_input,
                    pn.Spacer(height=14),
                    shell.background_linear_compute_button,
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "0px"},
                ),
                pn.Column(
                    pn.Column(
                        pn.Column(
                            pn.Spacer(height=62),
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
                            shell.background_sample_view_selector,
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
                            shell.background_linear_chi_plot_pane,
                            shell.background_linear_subtraction_plot_pane,
                            shell.background_sample_monte_carlo_placeholder_pane,
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
                    pn.Spacer(height=10),
                    pn.Row(
                        pn.layout.HSpacer(),
                        shell.background_sample_use_computed_t_button,
                        shell.background_sample_use_custom_t_button,
                        pn.layout.HSpacer(),
                        sizing_mode="fixed",
                        width=800,
                        styles={"align-items": "center", "gap": "12px"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                    styles={"flex": "0 0 800px", "overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=96),
                    shell.background_sample_summary_table,
                    pn.Spacer(height=12),
                    sizing_mode="fixed",
                    width=320,
                    styles={"flex": "0 0 320px", "min-width": "320px", "gap": "12px"},
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
                "<h3>Background Subtraction: Sample</h3>",
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
    shell.background_subtraction_vanadium_card = pn.Card(
        pn.Column(
            pn.Spacer(height=12),
            pn.Row(
                pn.Spacer(width=320),
                pn.Column(
                    pn.Row(
                        pn.layout.HSpacer(),
                        pn.Row(
                            shell.background_vanadium_method_select,
                            shell.background_vanadium_method_info_hover,
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
            pn.Spacer(height=16),
            pn.Row(
                pn.Column(
                    pn.Spacer(height=96),
                    pn.Row(
                        shell.background_vanadium_t_start,
                        shell.background_vanadium_t_stop,
                        shell.background_vanadium_t_step,
                        sizing_mode="stretch_width",
                    ),
                    pn.Spacer(height=12),
                    shell.background_vanadium_smoothing,
                    pn.Spacer(height=12),
                    shell.background_vanadium_ignore_points,
                    pn.Spacer(height=12),
                    shell.background_vanadium_use_custom_t_toggle,
                    pn.Spacer(height=10),
                    shell.background_vanadium_custom_t_input,
                    pn.Spacer(height=14),
                    shell.background_vanadium_compute_button,
                    sizing_mode="fixed",
                    width=320,
                    styles={"gap": "0px"},
                ),
                pn.Column(
                    pn.Column(
                        pn.Column(
                            pn.Spacer(height=62),
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
                            shell.background_vanadium_view_selector,
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
                            shell.background_vanadium_chi_plot_pane,
                            shell.background_vanadium_subtraction_plot_pane,
                            shell.background_vanadium_monte_carlo_placeholder_pane,
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
                    pn.Spacer(height=10),
                    pn.Row(
                        pn.layout.HSpacer(),
                        shell.background_vanadium_use_computed_t_button,
                        shell.background_vanadium_use_custom_t_button,
                        pn.layout.HSpacer(),
                        sizing_mode="fixed",
                        width=800,
                        styles={"align-items": "center", "gap": "12px"},
                    ),
                    sizing_mode="fixed",
                    width=800,
                    styles={"flex": "0 0 800px", "overflow": "hidden"},
                ),
                pn.Column(
                    pn.Spacer(height=96),
                    shell.background_vanadium_summary_table,
                    pn.Spacer(height=12),
                    sizing_mode="fixed",
                    width=320,
                    styles={"flex": "0 0 320px", "min-width": "320px", "gap": "12px"},
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
                "<h3>Background Subtraction: Vanadium</h3>",
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
    shell.background_linear_controls_card = pn.Card(
        pn.Row(
            shell.background_linear_t_start,
            shell.background_linear_t_stop,
            shell.background_linear_t_step,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_linear_smoothing,
            shell.background_linear_ignore_points,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_linear_compute_button,
            sizing_mode="stretch_width",
        ),
        pn.Row(
            shell.background_linear_t_mode,
            shell.background_linear_custom_t,
            sizing_mode="stretch_width",
        ),
        shell.background_linear_message,
        pn.Card(
            shell.background_linear_chi_plot_pane,
            title="Linear Combination: χ vs t",
            sizing_mode="stretch_width",
        ),
        pn.Card(
            shell.background_linear_subtraction_plot_pane,
            title="Linear Combination: Background-subtracted diffractogram",
            sizing_mode="stretch_width",
        ),
        title="Linear Combination",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.background_monte_carlo_card = pn.Card(
        pn.pane.Markdown(
            "Monte Carlo Simulation will be implemented in a future iteration.",
            sizing_mode="stretch_width",
        ),
        title="Monte Carlo Simulation",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_context_select = pn.widgets.Select(
        name="",
        options={"No exported background contexts yet.": ""},
        value="",
        sizing_mode="stretch_width",
        align="center",
        margin=(0, 0, 0, 20),
    )
    shell.normalization_custom_files_switch = pn.widgets.Switch(
        name="",
        value=False,
    )
    shell.normalization_custom_files_toggle_button = pn.widgets.Button(
        name="Use custom qdat override",
        button_type="primary",
        sizing_mode="fixed",
        width=220,
        height=34,
    )
    shell.normalization_custom_files_state_badge = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )
    shell.normalization_context_message = pn.pane.Alert(
        "Contexts are created by **Background → Export Data**.",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.normalization_context_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.normalization_context_summary = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )
    shell.normalization_source_mode = pn.widgets.RadioBoxGroup(
        name="Input Mode",
        inline=False,
        options=["Select File", "Write Path"],
        value="Select File",
        sizing_mode="stretch_width",
        margin=(15, 0, 0, 20),
    )
    shell.normalization_sample_qdat_dropdown = pn.widgets.Select(
        name="Sample `_sub.qdat`",
        options={"No qdat files found.": ""},
        value="",
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
        css_classes=["toscana-normalization-qdat-select"],
    )
    shell.normalization_vanadium_qdat_dropdown = pn.widgets.Select(
        name="Vanadium `_sub.qdat`",
        options={"No qdat files found.": ""},
        value="",
        sizing_mode="stretch_width",
        margin=(0, 0, 16, 20),
        css_classes=["toscana-normalization-qdat-select"],
    )
    shell.normalization_sample_qdat_path_input = pn.widgets.TextInput(
        name="Sample file path",
        placeholder=str(REPO_ROOT / "Projects" / "<project>" / QSPDATA_DIR / "sample_sub.qdat"),
        sizing_mode="stretch_width",
        margin=(0, 0, 12, 20),
        css_classes=["toscana-normalization-qdat-input"],
    )
    shell.normalization_vanadium_qdat_path_input = pn.widgets.TextInput(
        name="Vanadium file path",
        placeholder=str(REPO_ROOT / "Projects" / "<project>" / QSPDATA_DIR / "vanadium_sub.qdat"),
        sizing_mode="stretch_width",
        margin=(0, 0, 16, 20),
        css_classes=["toscana-normalization-qdat-input"],
    )
    shell.normalization_dropdown_column = pn.Column(
        shell.normalization_sample_qdat_dropdown,
        shell.normalization_vanadium_qdat_dropdown,
        sizing_mode="stretch_width",
    )
    shell.normalization_path_column = pn.Column(
        shell.normalization_sample_qdat_path_input,
        shell.normalization_vanadium_qdat_path_input,
        sizing_mode="stretch_width",
    )
    shell.normalization_source_stack = pn.Column(
        shell.normalization_dropdown_column,
        shell.normalization_path_column,
        sizing_mode="stretch_width",
    )
    shell.normalization_validate_button = pn.widgets.Button(
        name="Validate Selection",
        button_type="primary",
        sizing_mode="fixed",
        width=200,
        height=44,
        margin=(6, 0, 0, 20),
        css_classes=["toscana-normalization-validate-button"],
    )
    shell.normalization_selection_message = pn.pane.Alert(
        "Select sample and vanadium qdat files.",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.normalization_import_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_import_confirm_button = pn.widgets.Button(
        name="Copy Into Project",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=44,
        disabled=False,
    )
    shell.normalization_import_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
        disabled=False,
    )
    shell.normalization_import_card = pn.Card(
        shell.normalization_import_prompt,
        pn.Row(
            shell.normalization_import_confirm_button,
            shell.normalization_import_cancel_button,
        ),
        title="Import Required",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_adopt_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_adopt_confirm_button = pn.widgets.Button(
        name="Create Context",
        button_type="warning",
        sizing_mode="fixed",
        width=160,
        height=44,
        disabled=False,
    )
    shell.normalization_adopt_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
        disabled=False,
    )
    shell.normalization_adopt_card = pn.Card(
        shell.normalization_adopt_prompt,
        pn.Row(
            shell.normalization_adopt_confirm_button,
            shell.normalization_adopt_cancel_button,
        ),
        title="Context Not Found",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_fit_data_panel = pn.Card(
        title="Select Fitting Data",
        sizing_mode="stretch_width",
        styles={"flex": "1.16 1 0"},
        collapsible=False,
        css_classes=["toscana-normalization-fit-panel", "toscana-normalization-fit-panel--data"],
    )
    shell.normalization_fit_params_status = pn.pane.Markdown(
        "Select a background context to configure fit parameters.",
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_params_alert = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_fit_params_suggest_button = pn.widgets.Button(
        name="Suggest Initial Guess",
        button_type="light",
        sizing_mode="fixed",
        width=240,
        height=40,
        disabled=True,
        css_classes=["toscana-btn-suggest"],
        # Bokeh 3 widgets render in Shadow DOM; global CSS in assets/toscana.css
        # cannot reliably style the internal <button>. Use widget stylesheets.
        stylesheets=[
            """
            :host .bk-btn,
            :host(.bk-btn) {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
              padding-left: 16px;
              padding-right: 16px;
            }

            :host .bk-btn:hover {
              filter: brightness(1.04);
            }

            :host .bk-btn:focus,
            :host .bk-btn:active {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
            }

            :host(.bk-disabled) .bk-btn,
            :host .bk-btn:disabled,
            :host .bk-btn[disabled] {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
              opacity: 0.55;
            }
            """
        ],
    )
    shell.normalization_fit_params_run_button = pn.widgets.Button(
        name="Run Fit",
        button_type="primary",
        sizing_mode="fixed",
        width=110,
        height=40,
        disabled=True,
    )
    shell.normalization_fit_params_export_button = pn.widgets.Button(
        name="Export Data",
        button_type="success",
        sizing_mode="fixed",
        width=130,
        height=40,
        disabled=True,
    )

    shell.normalization_fit_params_export_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_params_export_confirm_button = pn.widgets.Button(
        name="Export",
        button_type="success",
        width=120,
        height=40,
        disabled=False,
    )
    shell.normalization_fit_params_export_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        width=120,
        height=40,
        disabled=False,
    )
    shell.normalization_fit_params_export_prompt_card = pn.Card(
        shell.normalization_fit_params_export_prompt,
        pn.Row(
            shell.normalization_fit_params_export_confirm_button,
            shell.normalization_fit_params_export_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Export Vanadium Self Fit",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )

    shell.normalization_sample_norm_status = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_sample_norm_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.normalization_export_folder_input = pn.widgets.TextInput(
        name="Export folder",
        value="normalization/",
        placeholder="normalization/",
        sizing_mode="stretch_width",
    )
    shell.normalization_export_button = pn.widgets.Button(
        name="Export Data",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.normalization_export_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.normalization_export_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_export_confirm_button = pn.widgets.Button(
        name="Proceed",
        button_type="danger",
        sizing_mode="fixed",
        width=140,
        height=44,
        disabled=False,
    )
    shell.normalization_export_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=44,
        disabled=False,
    )
    shell.normalization_export_prompt_card = pn.Card(
        shell.normalization_export_prompt,
        pn.Row(
            shell.normalization_export_confirm_button,
            shell.normalization_export_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Confirm Export",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )
    shell.normalization_export_card = pn.Card(
        pn.Column(
            shell.normalization_export_folder_input,
            pn.Row(
                shell.normalization_export_button,
                shell.normalization_export_info_hover,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        shell.normalization_export_prompt_card,
        title="Export Data",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
        styles={"overflow": "visible", "margin-bottom": "180px"},
        visible=True,
    )

    shell.normalization_fit_params_action_hint = pn.pane.Markdown(
        "_Fit runs in-app (does not write to the project). Export writes `normalization/<context_id>/vanadium_self_fit.qdat`._",
        sizing_mode="stretch_width",
    )

    shell.normalization_fit_params_results = pn.pane.Markdown(
        "No fit has been run yet.",
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_params_plot_mode = pn.widgets.RadioButtonGroup(
        name="",
        options=["Fit overlay", "Differential cross section"],
        value="Fit overlay",
        button_type="light",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_params_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="stretch_width",
        config={"responsive": True},
        height=340,
    )

    shell.normalization_vanadium_self_fit_preview_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=[
            """
            input[type="checkbox"] {
              appearance: none;
              -webkit-appearance: none;
              width: 52px;
              height: 28px;
              border-radius: 999px;
              background: rgba(148, 163, 184, 0.35);
              border: 1px solid rgba(148, 163, 184, 0.55);
              position: relative;
              cursor: pointer;
              transition: background 180ms ease, border-color 180ms ease;
              box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
            }

            input[type="checkbox"]::before {
              content: "";
              position: absolute;
              top: 3px;
              left: 3px;
              width: 22px;
              height: 22px;
              border-radius: 999px;
              background: rgba(255, 255, 255, 0.92);
              box-shadow: 0 6px 16px rgba(15, 23, 42, 0.18);
              transition: transform 180ms cubic-bezier(0.2, 0.7, 0.2, 1);
            }

            input[type="checkbox"]:checked {
              background: rgba(37, 99, 235, 0.26);
              border-color: rgba(37, 99, 235, 0.42);
            }

            input[type="checkbox"]:checked::before {
              transform: translateX(24px);
            }

            input[type="checkbox"]:focus-visible {
              outline: none;
              box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.28);
            }
            """
        ],
    )
    shell.normalization_vanadium_self_fit_preview_view_selector = pn.Row(
        # 1. The Text Label
        pn.pane.Markdown(
            "Switch View",
            margin=(0, 10, 0, 0),
            align="center",
            styles={
                "font-size": "0.86rem", 
                "font-weight": "700", 
                "color": "rgba(15, 23, 42, 0.82)"
            },
        ),
        # 2. The Switch Wrapper (Adjust the '5' below to nudge it down further)
        pn.Column(
            shell.normalization_vanadium_self_fit_preview_view_switch,
            margin=(45, 0, 0, 0),  # Increase the 5 to 8 or 10 if it's still too high
            align="center",
            sizing_mode="fixed"
        ),
        # Row Configuration
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center", 
            "justify-content": "flex-end"
        },
    )
    shell.normalization_vanadium_self_fit_preview_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    # Fit-result table shown next to the vanadium self-fit preview plot (static HTML, styled via global CSS).
    shell.normalization_vanadium_self_fit_preview_fit_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    shell.normalization_fit_params_A_pinned = pn.widgets.Checkbox(
        name="Fix",
        value=True,
        sizing_mode="fixed",
        width=58,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-fix-toggle"],
    )

    def _fit_param_tooltip(text: str) -> pn.widgets.TooltipIcon:
        return pn.widgets.TooltipIcon(
            value=(
                "<div style=\"max-width: 320px; line-height: 1.4; white-space: normal; "
                "overflow-wrap: anywhere; word-break: break-word;\">"
                f"{text}"
                "</div>"
            ),
        )

    shell.normalization_fit_params_a0_info = _fit_param_tooltip(
        "Polynomial constant term. Defaults to 1 (no scaling)."
    )
    shell.normalization_fit_params_a1_info = _fit_param_tooltip(
        "Polynomial linear coefficient in Q. Defaults to 0."
    )
    shell.normalization_fit_params_a2_info = _fit_param_tooltip(
        "Polynomial quadratic coefficient in Q. Defaults to 0."
    )
    shell.normalization_fit_params_A_info = _fit_param_tooltip(
        "Mass number used by the inelastic model. Default is 51 for Vanadium."
    )
    shell.normalization_fit_params_lowQ_info = _fit_param_tooltip(
        "Low-Q asymptote of the inelastic model as Q → 0."
    )
    shell.normalization_fit_params_Q0_info = _fit_param_tooltip(
        "Inflection point of the inelastic sigmoid in Q."
    )
    shell.normalization_fit_params_dQ_info = _fit_param_tooltip(
        "Transition width of the inelastic sigmoid."
    )

    def _fit_float(value: float) -> pn.widgets.LiteralInput:
        return pn.widgets.LiteralInput(
            name="",
            value=float(value),
            type=(int, float),
            sizing_mode="fixed",
            width=96,
            height=32,
            margin=(0, 0, 0, 0),
        )

    shell.normalization_fit_params_a0_value = _fit_float(1.0)
    shell.normalization_fit_params_a1_value = _fit_float(0.0)
    shell.normalization_fit_params_a2_value = _fit_float(0.0)
    shell.normalization_fit_params_A_value = _fit_float(51.0)
    shell.normalization_fit_params_lowQ_value = _fit_float(0.4)
    shell.normalization_fit_params_Q0_value = _fit_float(7.4)
    shell.normalization_fit_params_dQ_value = _fit_float(2.4)

    def _fit_bound(value: float) -> pn.widgets.LiteralInput:
        return pn.widgets.LiteralInput(
            name="",
            value=float(value),
            type=(int, float),
            sizing_mode="fixed",
            width=88,
            height=32,
            margin=(0, 0, 0, 0),
        )

    bound_wide = 1e6
    shell.normalization_fit_params_a0_min = _fit_bound(-bound_wide)
    shell.normalization_fit_params_a0_max = _fit_bound(bound_wide)
    shell.normalization_fit_params_a1_min = _fit_bound(-bound_wide)
    shell.normalization_fit_params_a1_max = _fit_bound(bound_wide)
    shell.normalization_fit_params_a2_min = _fit_bound(-bound_wide)
    shell.normalization_fit_params_a2_max = _fit_bound(bound_wide)
    shell.normalization_fit_params_A_min = _fit_bound(51.0)
    shell.normalization_fit_params_A_max = _fit_bound(51.0)
    shell.normalization_fit_params_A_value.disabled = True
    shell.normalization_fit_params_A_min.disabled = True
    shell.normalization_fit_params_A_max.disabled = True
    shell.normalization_fit_params_lowQ_min = _fit_bound(0.0)
    shell.normalization_fit_params_lowQ_max = _fit_bound(bound_wide)
    shell.normalization_fit_params_Q0_min = _fit_bound(0.0)
    shell.normalization_fit_params_Q0_max = _fit_bound(25.0)
    shell.normalization_fit_params_dQ_min = _fit_bound(1e-3)
    shell.normalization_fit_params_dQ_max = _fit_bound(25.0)

    def _fit_param_row(
        label: str,
        info_widget: object,
        value_widget: object,
        *,
        adornment: object | None = None,
    ) -> pn.Row:
        # Use a pure upward nudge. Symmetric top/bottom margins can cancel out under flex centering.
        label_margin = (-14, 0, 0, 0)
        icon_margin = (2, 0, 0, 0)
        label_block_items = [
            pn.pane.Markdown(
                label,
                margin=label_margin,
                sizing_mode="fixed",
                width=54,
            ),
            pn.Column(info_widget, margin=icon_margin),
        ]
        if adornment is not None:
            label_block_items.append(adornment)
        return pn.Row(
            pn.Row(
                *label_block_items,
                sizing_mode="stretch_width",
                css_classes=["toscana-normalization-fit-param-label"],
                styles={"align-items": "center"},
            ),
            value_widget,
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-param-row"],
            styles={"align-items": "center"},
        )

    _bounds_param_labels = [
        "a0",
        "a1",
        "a2",
        "A",
        "lowQ",
        "Q0",
        "dQ",
    ]
    _bounds_min_widgets = [
        shell.normalization_fit_params_a0_min,
        shell.normalization_fit_params_a1_min,
        shell.normalization_fit_params_a2_min,
        shell.normalization_fit_params_A_min,
        shell.normalization_fit_params_lowQ_min,
        shell.normalization_fit_params_Q0_min,
        shell.normalization_fit_params_dQ_min,
    ]
    _bounds_max_widgets = [
        shell.normalization_fit_params_a0_max,
        shell.normalization_fit_params_a1_max,
        shell.normalization_fit_params_a2_max,
        shell.normalization_fit_params_A_max,
        shell.normalization_fit_params_lowQ_max,
        shell.normalization_fit_params_Q0_max,
        shell.normalization_fit_params_dQ_max,
    ]

    _bounds_header_margin = (-9, 0, 0, 0)
    shell.normalization_fit_params_bounds_grid = pn.GridBox(
        pn.pane.Markdown("**Parameter**", margin=_bounds_header_margin),
        *[pn.pane.Markdown(label, margin=(-8, 0, 0, 0)) for label in _bounds_param_labels],
        pn.pane.Markdown("**Min**", margin=_bounds_header_margin),
        *_bounds_min_widgets,
        pn.pane.Markdown("**Max**", margin=_bounds_header_margin),
        *_bounds_max_widgets,
        ncols=1 + len(_bounds_param_labels),
        sizing_mode="stretch_width",
        css_classes=[
            "toscana-normalization-fit-bounds-grid",
            "toscana-normalization-fit-bounds-grid--horizontal",
        ],
    )
    shell.normalization_fit_params_grid = shell.normalization_fit_params_bounds_grid

    _fit_section_box_styles = {
        "border-radius": "16px",
        "box-shadow": "none",
        "border": "1px solid rgba(148, 163, 184, 0.22)",
        "background": "rgba(248, 250, 252, 0.72)",
        "padding": "12px 14px",
    }

    shell.normalization_fit_params_core_polynomial = pn.Column(
        pn.pane.Markdown(
            "Polynomial",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        _fit_param_row("`a0`", shell.normalization_fit_params_a0_info, shell.normalization_fit_params_a0_value),
        _fit_param_row("`a1`", shell.normalization_fit_params_a1_info, shell.normalization_fit_params_a1_value),
        _fit_param_row("`a2`", shell.normalization_fit_params_a2_info, shell.normalization_fit_params_a2_value),
        sizing_mode="stretch_width",
        styles=_fit_section_box_styles,
        css_classes=["toscana-normalization-fit-section-card"],
    )
    shell.normalization_fit_params_core_inelastic = pn.Column(
        pn.pane.Markdown(
            "Inelastic",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        _fit_param_row(
            "`A`",
            shell.normalization_fit_params_A_info,
            pn.Row(
                shell.normalization_fit_params_A_pinned,
                shell.normalization_fit_params_A_value,
                sizing_mode="fixed",
                styles={"align-items": "center", "justify-content": "flex-end", "gap": "10px"},
            ),
        ),
        _fit_param_row(
            "`lowQ`",
            shell.normalization_fit_params_lowQ_info,
            shell.normalization_fit_params_lowQ_value,
        ),
        _fit_param_row("`Q0`", shell.normalization_fit_params_Q0_info, shell.normalization_fit_params_Q0_value),
        _fit_param_row("`dQ`", shell.normalization_fit_params_dQ_info, shell.normalization_fit_params_dQ_value),
        sizing_mode="stretch_width",
        styles=_fit_section_box_styles,
        css_classes=["toscana-normalization-fit-section-card"],
    )
    shell.normalization_fit_params_core_sections = pn.FlexBox(
        shell.normalization_fit_params_core_polynomial,
        shell.normalization_fit_params_core_inelastic,
        gap="16px",
        flex_wrap="wrap",
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-core-sections"],
    )
    shell.normalization_fit_params_bounds_card = pn.Column(
        pn.pane.Markdown(
            "Advanced bounds",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        pn.pane.Markdown(
            "Use this only when the suggested or current parameter range needs manual tightening.",
            sizing_mode="stretch_width",
        ),
        shell.normalization_fit_params_bounds_grid,
        sizing_mode="stretch_width",
        visible=False,
        margin=(12, 0, 0, 0),
        styles={**_fit_section_box_styles, "overflow-x": "auto"},
        css_classes=["toscana-normalization-fit-bounds-card"],
    )
    shell.normalization_fit_params_plot_card = pn.Card(
        pn.Row(
            pn.pane.Markdown(
                "Fit output",
                sizing_mode="stretch_width",
                css_classes=["toscana-normalization-fit-section-title"],
            ),
            sizing_mode="stretch_width",
        ),
        shell.normalization_fit_params_results,
        shell.normalization_fit_params_plot_mode,
        shell.normalization_fit_params_plot_pane,
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-output-card"],
    )
    shell.normalization_fit_params_setup_card = pn.Card(
        shell.normalization_fit_params_status,
        shell.normalization_fit_params_alert,
        pn.Row(
            shell.normalization_fit_params_suggest_button,
            shell.normalization_fit_params_run_button,
            pn.Spacer(),
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-action-row"],
        ),
        shell.normalization_fit_params_action_hint,
        pn.Spacer(height=0),
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-setup-card"],
    )

    shell.normalization_fit_params_status_card = pn.Card(
        shell.normalization_fit_params_status,
        shell.normalization_fit_params_alert,
        sizing_mode="stretch_width",
        hide_header=True,
        css_classes=["toscana-normalization-fit-setup-card"],
    )

    shell.normalization_fit_params_bounds_toggle = pn.widgets.Toggle(
        name="Advanced bounds",
        value=False,
        button_type="light",
        sizing_mode="stretch_width",
        height=36,
    )

    shell.normalization_fit_params_panel = pn.Card(
        pn.pane.Markdown(
            "Define the fitting parameters and bounds for `toscana.models.scattering.vanaQdep`.",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-panel-lead"],
        ),
        pn.pane.Markdown(
            "Begin with the suggested estimate, adjust only the parameters that need intervention, and use advanced bounds only when the fit needs tighter guidance.",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-panel-copy"],
        ),
        shell.normalization_fit_params_setup_card,
        shell.normalization_fit_params_core_sections,
        shell.normalization_fit_params_bounds_card,
        shell.normalization_fit_params_plot_card,
        title="Select Fitting Parameters",
        sizing_mode="stretch_width",
        styles={"flex": "0.92 1 0"},
        collapsible=False,
        css_classes=["toscana-normalization-fit-panel", "toscana-normalization-fit-panel--params"],
    )

    shell.normalization_fit_data_selection_mode = pn.widgets.RadioButtonGroup(
        name="",
        options={
            "Percentile band": "percentile_band",
            "Manual window": "manual_window",
        },
        value="percentile_band",
        button_type="light",
        sizing_mode="stretch_width",
    )

    shell.normalization_fit_data_use_sliders = pn.widgets.Toggle(
        name="Use sliders",
        value=True,
        button_type="light",
        sizing_mode="fixed",
        width=140,
    )

    shell.normalization_fit_data_q_tail_low = pn.widgets.FloatInput(
        name="Q start",
        value=4.0,
        step=0.1,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_q_tail_high = pn.widgets.FloatInput(
        name="Q end",
        value=20.0,
        step=0.1,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_min_percentile = pn.widgets.IntInput(
        name="Lower percentile",
        value=0,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_max_percentile = pn.widgets.IntInput(
        name="Upper percentile",
        value=95,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
    )

    shell.normalization_fit_data_q_tail_low_slider = pn.widgets.FloatSlider(
        name="Q start",
        value=shell.normalization_fit_data_q_tail_low.value,
        start=0.0,
        end=25.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_q_tail_high_slider = pn.widgets.FloatSlider(
        name="Q end",
        value=shell.normalization_fit_data_q_tail_high.value,
        start=0.0,
        end=25.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_min_percentile_slider = pn.widgets.IntSlider(
        name="Lower percentile",
        value=shell.normalization_fit_data_min_percentile.value,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_max_percentile_slider = pn.widgets.IntSlider(
        name="Upper percentile puto",
        value=shell.normalization_fit_data_max_percentile.value,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_fit_data_define_controls = pn.Column(
        shell.normalization_fit_data_q_tail_low,
        shell.normalization_fit_data_q_tail_high,
        shell.normalization_fit_data_min_percentile,
        shell.normalization_fit_data_max_percentile,
        sizing_mode="stretch_width",
    )

    shell.normalization_fit_data_q_min = pn.widgets.FloatInput(
        name="Q min",
        value=0.5,
        step=0.1,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_q_max = pn.widgets.FloatInput(
        name="Q max",
        value=23.5,
        step=0.1,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_y_min = pn.widgets.FloatInput(
        name="Intensity min",
        value=17200.0,
        step=1.0,
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_y_max = pn.widgets.FloatInput(
        name="Intensity max",
        value=18200.0,
        step=1.0,
        sizing_mode="stretch_width",
    )

    shell.normalization_fit_data_q_min_slider = pn.widgets.FloatSlider(
        name="Q min",
        value=shell.normalization_fit_data_q_min.value,
        start=0.0,
        end=25.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_q_max_slider = pn.widgets.FloatSlider(
        name="Q max",
        value=shell.normalization_fit_data_q_max.value,
        start=0.0,
        end=25.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_y_min_slider = pn.widgets.FloatSlider(
        name="Intensity min",
        value=shell.normalization_fit_data_y_min.value,
        start=0.0,
        end=20000.0,
        step=10.0,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_y_max_slider = pn.widgets.FloatSlider(
        name="Intensity max",
        value=shell.normalization_fit_data_y_max.value,
        start=0.0,
        end=20000.0,
        step=10.0,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_fit_data_hardcoded_controls = pn.Column(
        shell.normalization_fit_data_q_min,
        shell.normalization_fit_data_q_max,
        shell.normalization_fit_data_y_min,
        shell.normalization_fit_data_y_max,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.normalization_fit_data_status = pn.pane.Markdown(
        "Select a background context with `vanadium_sub.qdat` to proceed.",
        sizing_mode="stretch_width",
    )
    shell.normalization_fit_data_alert = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.normalization_fit_data_ui_summary = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )
    shell.normalization_fit_data_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="stretch_width",
        config={"responsive": True},
        height=460,
    )
    shell.normalization_fit_data_redesign_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.normalization_fit_data_redesign_switch_input_mode = pn.widgets.Button(
        name="Switch Input Mode",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.normalization_fit_data_redesign_switch_method = pn.widgets.Button(
        name="Switch Method",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.normalization_fit_data_redesign_mode_chips = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    shell.normalization_fit_data_redesign_window_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=292,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    shell.normalization_fit_data_redesign_top_controls = pn.Row(
        shell.normalization_fit_data_redesign_switch_input_mode,
        shell.normalization_fit_data_redesign_switch_method,
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, -250),
        styles={
        "align-items": "center",
        "justify-content": "center",
        "gap": "14px",
        },
        align="center",
    )

    shell.normalization_fit_data_redesign_right_tray = pn.Column(
        pn.Spacer(height=150),
        shell.normalization_fit_data_redesign_window_table,
        pn.Spacer(),
        sizing_mode="stretch_height",
        width=292,
        min_width=292,
        styles={
            "padding": "0",
        },
        visible=True,
    )

    _fit_data_numeric_label_styles = {
        "color": "rgba(15, 23, 42, 0.95)",
        "font-family": "inherit",
        "font-size": "0.86rem",
        "font-weight": "700",
        "line-height": "1.1",
    }

    shell.normalization_fit_data_redesign_q_start_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.normalization_fit_data_q_tail_low.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.normalization_fit_data_redesign_q_end_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.normalization_fit_data_q_tail_high.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.normalization_fit_data_redesign_q_input_row = pn.Row(
        pn.Row(
            pn.pane.HTML("Q start:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.normalization_fit_data_redesign_q_start_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        pn.Spacer(),
        pn.Row(
            pn.pane.HTML("Q end:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.normalization_fit_data_redesign_q_end_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        sizing_mode="fixed",
        width=600,
        margin=(0, 0, 0, 0),
        styles={"align-items": "center"},
        visible=False,
    )

    shell.normalization_fit_data_redesign_q_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.normalization_fit_data_q_tail_low.value),
            float(shell.normalization_fit_data_q_tail_high.value),
        ],
        start=0.0,
        end=25.0,
        step=0.05,
        orientation="horizontal",
        label_display="flex",
        lower_label="Q start",
        upper_label="Q end",
        sizing_mode="fixed",
        width=600,
        height=58,
        visible=False,
    )

    shell.normalization_fit_data_redesign_vertical_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.normalization_fit_data_min_percentile.value),
            float(shell.normalization_fit_data_max_percentile.value),
        ],
        start=0,
        end=100,
        step=1,
        orientation="vertical",
        sizing_mode="fixed",
        width=72,
        height=394,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.normalization_fit_data_redesign_vertical_upper_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.normalization_fit_data_redesign_vertical_upper_input = pn.widgets.FloatInput(
        name="",
        value=0.0,
        step=1.0,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.normalization_fit_data_redesign_vertical_lower_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.normalization_fit_data_redesign_vertical_lower_input = pn.widgets.FloatInput(
        name="",
        value=0.0,
        step=1.0,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )

    shell.normalization_fit_data_redesign_vertical_axis_controls = pn.Row(
        pn.pane.HTML(
            """
            <div style="
                height: 450px;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <div style="
                    transform: rotate(-90deg);
                    white-space: nowrap;
                    font-size: 0.84rem;
                    font-weight: 700;
                letter-spacing: 0.02em;
                text-transform: uppercase;
                color: rgba(71, 85, 105, 0.86);
            font-size: 0.78rem;
            ">Intensity filter</div>
            </div>
            """,
            sizing_mode="fixed",
            width=26,
            height=450,
            margin=(0, 0, 0, 0),
        ),
        pn.Column(
            sizing_mode="fixed",
            width=154,
            height=450,
            styles={"align-items": "center"},
            margin=(0, 0, 0, 0),
            objects=[
                shell.normalization_fit_data_redesign_vertical_upper_value,
                shell.normalization_fit_data_redesign_vertical_upper_input,
                shell.normalization_fit_data_redesign_vertical_range_slider,
                shell.normalization_fit_data_redesign_vertical_lower_value,
                shell.normalization_fit_data_redesign_vertical_lower_input,
            ],
        ),
        sizing_mode="fixed",
        width=320,
        height=450,
        styles={
            "align-items": "flex-start",
            "box-sizing": "border-box",
            "gap": "4px",
            "padding": "0px",
        },
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--vertical",
        ],
        visible=False,
    )

    shell.normalization_fit_data_redesign_horizontal_axis_controls = pn.Column(
        pn.pane.Markdown(
            "Q filter",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-axis-title"],
        ),
        shell.normalization_fit_data_redesign_q_input_row,
        pn.Row(
            shell.normalization_fit_data_redesign_q_range_slider,
            sizing_mode="fixed",
            width=600,
            styles={"gap": "0px"},
        ),
        sizing_mode="fixed",
        width=600,
        visible=False,
        margin=(0, 0, 0, 0),
        styles={"box-sizing": "border-box", "padding": "0px"},
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--horizontal",
        ],
    )
    shell.normalization_fit_data_vertical_axis_controls = pn.Column(
        pn.pane.Markdown(
            "Intensity filter",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-axis-title"],
        ),
        shell.normalization_fit_data_min_percentile_slider,
        shell.normalization_fit_data_max_percentile_slider,
        shell.normalization_fit_data_y_min_slider,
        shell.normalization_fit_data_y_max_slider,
        sizing_mode="stretch_height",
        width=228,
        min_width=208,
        visible=False,
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--vertical",
        ],
    )
    shell.normalization_fit_data_horizontal_axis_controls = pn.Column(
        pn.pane.Markdown(
            "Q filter",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-axis-title"],
        ),
        pn.Row(
            shell.normalization_fit_data_q_tail_low_slider,
            shell.normalization_fit_data_q_tail_high_slider,
            shell.normalization_fit_data_q_min_slider,
            shell.normalization_fit_data_q_max_slider,
            sizing_mode="stretch_width",
        ),
        sizing_mode="stretch_width",
        visible=False,
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--horizontal",
        ],
    )
    shell.normalization_fit_data_input_menu_toggle = pn.widgets.Toggle(
        name="Show controls",
        value=False,
        button_type="light",
        sizing_mode="fixed",
        width=150,
        height=36,
    )
    shell.normalization_fit_data_input_tray = pn.Card(
        pn.Row(
            shell.normalization_fit_data_selection_mode,
            shell.normalization_fit_data_use_sliders,
            sizing_mode="stretch_width",
        ),
        shell.normalization_fit_data_define_controls,
        shell.normalization_fit_data_hardcoded_controls,
        title="Numeric Controls",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-normalization-input-tray"],
    )
    shell.normalization_fit_data_setup_card = pn.Card(
        pn.pane.Markdown(
            "Start from the plot, keep the visible window broad enough to capture the valid vanadium region, and open the input menu only when you need exact numeric control.",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-panel-copy"],
        ),
        shell.normalization_fit_data_ui_summary,
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-setup-card"],
    )
    shell.normalization_fit_data_feedback_card = pn.Card(
        shell.normalization_fit_data_status,
        shell.normalization_fit_data_alert,
        title="Current Selection",
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-feedback-card"],
    )
    shell.normalization_fit_data_workspace_card = pn.Card(
        pn.Row(
            shell.normalization_fit_data_vertical_axis_controls,
            pn.Column(
                shell.normalization_fit_data_plot_pane,
                shell.normalization_fit_data_horizontal_axis_controls,
                pn.Row(
                    pn.Spacer(),
                    shell.normalization_fit_data_input_menu_toggle,
                    pn.Spacer(),
                    sizing_mode="stretch_width",
                ),
                shell.normalization_fit_data_input_tray,
                shell.normalization_fit_data_feedback_card,
                sizing_mode="stretch_width",
                css_classes=["toscana-normalization-plot-stage"],
            ),
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-data-workspace"],
        ),
        title="Selection Workspace",
        sizing_mode="stretch_width",
        css_classes=["toscana-normalization-fit-workspace-card"],
    )

    shell.normalization_fit_data_panel[:] = [
        pn.pane.Markdown(
            "Choose the fitting window for the vanadium diffractogram.",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-panel-lead"],
        ),
        shell.normalization_fit_data_setup_card,
        shell.normalization_fit_data_workspace_card,
    ]

    # ------------------------------
    # Self scattering (Low-Q extrapolation)
    # ------------------------------
    shell.self_context_select = pn.widgets.Select(
        name="",
        options={"No exported background contexts yet.": ""},
        value="",
        sizing_mode="stretch_width",
        align="center",
        margin=(0, 0, 0, 20),
    )
    shell.self_context_message = pn.pane.Alert(
        "Select a background context that has been normalized (Normalisation → Export Data).",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.self_context_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.self_context_summary = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    # ------------------------------
    # Fourier Transform (FT) - data loading
    # ------------------------------
    shell.ft_context_select = pn.widgets.Select(
        name="",
        options={"No exported background contexts yet.": ""},
        value="",
        sizing_mode="stretch_width",
        align="center",
        margin=(0, 0, 0, 20),
    )
    shell.ft_context_message = pn.pane.Alert(
        "Select a context with an exported `SOQ_qdat` (Self → Export Static Structure Factor).",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.ft_context_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.ft_context_summary = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    # ------------------------------
    # Back Fourier Transform (BFT) - data loading (mirrors FT header layout)
    # ------------------------------
    shell.bft_context_select = pn.widgets.Select(
        name="",
        options={"No exported background contexts yet.": ""},
        value="",
        sizing_mode="stretch_width",
        align="center",
        margin=(0, 0, 0, 20),
    )
    shell.bft_context_message = pn.pane.Alert(
        "Select a context with exported FT inputs (in-session FT confirmation or FT Real Space export).",
        alert_type="secondary",
        sizing_mode="stretch_width",
    )
    shell.bft_context_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )
    shell.bft_context_summary = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    # ------------------------------
    # Back Fourier Transform (BFT) - controls + results
    # ------------------------------
    shell.bft_iterations_input = pn.widgets.IntInput(
        name="Number of iterations",
        value=4,
        step=1,
        start=0,
        sizing_mode="stretch_width",
    )
    shell.bft_run_button = pn.widgets.Button(
        name="Run Back-FT",
        button_type="primary",
        sizing_mode="fixed",
        width=220,
        height=48,
        disabled=False,
    )
    shell.bft_run_status = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    shell.bft_iterations_warning = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.bft_iterations_confirm_button = pn.widgets.Button(
        name="Confirm",
        button_type="danger",
        width=120,
        height=40,
        disabled=False,
    )
    shell.bft_iterations_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        width=120,
        height=40,
        disabled=False,
    )
    shell.bft_iterations_warning_card = pn.Card(
        shell.bft_iterations_warning,
        pn.Row(
            shell.bft_iterations_confirm_button,
            shell.bft_iterations_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Confirm Iterations",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )

    shell.bft_animation_counter = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
    )
    shell.bft_animation_player = pn.widgets.Player(
        name="",
        start=0,
        end=0,
        value=0,
        interval=600,
        loop_policy="loop",
        sizing_mode="fixed",
        width=800,
        disabled=True,
    )
    shell.bft_animation_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )
    shell.bft_final_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )
    shell.bft_final_prev_plot_button = pn.widgets.Button(
        name="Prev Plot",
        icon="chevron-left",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.bft_final_next_plot_button = pn.widgets.Button(
        name="Next Plot",
        icon="chevron-right",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.bft_final_plot_view_label = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
        disable_math=False,
    )

    shell.ft_title_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.ft_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(40, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=shell.normalization_vanadium_self_fit_preview_view_switch.stylesheets
        if hasattr(shell, "normalization_vanadium_self_fit_preview_view_switch")
        else [],
        disabled=True,
    )
    shell.ft_view_label = pn.pane.Markdown(
        "Show Static Structure Factor",
        margin=(0, 10, 0, 0),
        align="center",
        styles={
            "font-size": "0.86rem",
            "font-weight": "700",
            "color": "rgba(15, 23, 42, 0.82)",
        },
    )
    shell.ft_view_selector = pn.Row(
        shell.ft_view_label,
        pn.Column(
            shell.ft_view_switch,
            margin=(5, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-end",
        },
    )

    # ------------------------------
    # Fourier Transform (FT) - effective atomic density (rho)
    # ------------------------------
    shell.ft_rho_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    # ------------------------------
    # Fourier Transform (FT) - real space functions
    # ------------------------------
    shell.ft_real_space_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.ft_export_folder_input = pn.widgets.TextInput(
        name="Export folder",
        value="ft/",
        placeholder="ft/",
        sizing_mode="stretch_width",
    )
    shell.ft_export_button = pn.widgets.Button(
        name="Export Data",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.ft_export_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.ft_export_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.ft_export_confirm_button = pn.widgets.Button(
        name="Export",
        button_type="success",
        sizing_mode="fixed",
        width=120,
        height=40,
        disabled=False,
    )
    shell.ft_export_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=40,
        disabled=False,
    )
    shell.ft_export_prompt_card = pn.Card(
        shell.ft_export_prompt,
        pn.Row(
            shell.ft_export_confirm_button,
            shell.ft_export_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Confirm Export",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )
    shell.ft_export_card = pn.Card(
        pn.Column(
            shell.ft_export_folder_input,
            pn.Row(
                shell.ft_export_button,
                shell.ft_export_info_hover,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        shell.ft_export_prompt_card,
        title="Export Data",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
        styles={"overflow": "visible", "margin-bottom": "180px"},
        visible=True,
    )

    shell.ft_real_space_prev_block_button = pn.widgets.Button(
        name="Prev Block",
        icon="chevron-left",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.ft_real_space_next_block_button = pn.widgets.Button(
        name="Next Block",
        icon="chevron-right",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.ft_real_space_prev_plot_button = pn.widgets.Button(
        name="Prev Plot",
        icon="chevron-left",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.ft_real_space_next_plot_button = pn.widgets.Button(
        name="Next Plot",
        icon="chevron-right",
        button_type="light",
        sizing_mode="fixed",
        width=140,
        height=40,
        disabled=True,
    )
    shell.ft_real_space_block_view_label = pn.pane.Markdown(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
    )
    shell.ft_real_space_plot_view_label = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={"text-align": "center"},
        disable_math=False,
    )

    shell.ft_rho_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(40, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=shell.normalization_vanadium_self_fit_preview_view_switch.stylesheets
        if hasattr(shell, "normalization_vanadium_self_fit_preview_view_switch")
        else [],
        disabled=True,
    )
    shell.ft_rho_view_label = pn.pane.Markdown(
        "Switch to Run Fit",
        margin=(0, 10, 0, 0),
        align="center",
        styles={
            "font-size": "0.86rem",
            "font-weight": "700",
            "color": "rgba(15, 23, 42, 0.82)",
        },
    )
    shell.ft_rho_view_selector = pn.Row(
        shell.ft_rho_view_label,
        pn.Column(
            shell.ft_rho_view_switch,
            margin=(5, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-end",
        },
    )

    shell.ft_rho_series_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=shell.normalization_vanadium_self_fit_preview_view_switch.stylesheets
        if hasattr(shell, "normalization_vanadium_self_fit_preview_view_switch")
        else [],
        disabled=True,
    )
    shell.ft_rho_series_label = pn.pane.Markdown(
        "Switch to G(R) Lorch",
        margin=(0, 10, 0, 0),
        align="center",
        styles={
            "font-size": "0.86rem",
            "font-weight": "700",
            "color": "rgba(15, 23, 42, 0.82)",
        },
    )
    shell.ft_rho_series_selector = pn.Row(
        shell.ft_rho_series_label,
        pn.Column(
            shell.ft_rho_series_switch,
            margin=(45, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "center",
        },
    )

    shell.ft_rho_r_range_slider = ToscanaRangeSlider(
        value=[0.0, 1.0],
        start=0.0,
        end=1.0,
        step=0.1,
        orientation="horizontal",
        label_display="flex",
        lower_label="R start",
        upper_label="R end",
        sizing_mode="fixed",
        width=600,
        height=58,
        disabled=True,
    )

    shell.ft_rho_r_filter_info = pn.widgets.TooltipIcon(
        value=(
            "<div style=\"max-width: 320px; line-height: 1.4; white-space: normal; "
            "overflow-wrap: anywhere; word-break: break-word;\">"
            "R filter is disabled in Run Fit view. Switch to Selection to adjust."
            "</div>"
        ),
        sizing_mode="fixed",
        width=22,
        height=22,
        margin=(3, 0, 0, 6),
    )

    shell.ft_rho_r_filter_controls = pn.Column(
        pn.Row(
            pn.pane.Markdown(
                "R filter",
                sizing_mode="fixed",
                margin=(0, 0, 0, 0),
                css_classes=["toscana-normalization-axis-title"],
            ),
            shell.ft_rho_r_filter_info,
            sizing_mode="stretch_width",
            styles={"align-items": "center"},
        ),
        pn.Row(
            shell.ft_rho_r_range_slider,
            sizing_mode="fixed",
            width=600,
            styles={"gap": "0px"},
        ),
        sizing_mode="fixed",
        width=600,
        margin=(0, 0, 0, 0),
        styles={"box-sizing": "border-box", "padding": "0px"},
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--horizontal",
        ],
        visible=True,
    )

    shell.ft_rho_window_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )
    shell.ft_rho_fit_result_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    shell.ft_rho_resolve_density_button = pn.widgets.Button(
        name="Resolve Effective Atomic Density",
        button_type="primary",
        sizing_mode="fixed",
        width=280,
        height=48,
        disabled=True,
    )

    shell.ft_rho_choice_lorch = pn.widgets.RadioBoxGroup(
        name="",
        options={
            "Use Original $\rho_N$ N/A": "original",
            "Use Fitted $\rho_N$ N/A": "fitted",
            "Use Custom Value": "custom",
        },
        value=None,
        sizing_mode="stretch_width",
    )
    shell.ft_rho_custom_lorch = pn.widgets.FloatInput(
        name="",
        value=None,
        sizing_mode="fixed",
        width=140,
        visible=False,
    )

    shell.ft_rho_choice_no_lorch = pn.widgets.RadioBoxGroup(
        name="",
        options={
            "Use Original $\rho_N$ N/A": "original",
            "Use Fitted $\rho_N$ N/A": "fitted",
            "Use Custom Value": "custom",
        },
        value=None,
        sizing_mode="stretch_width",
    )
    shell.ft_rho_custom_no_lorch = pn.widgets.FloatInput(
        name="",
        value=None,
        sizing_mode="fixed",
        width=140,
        visible=False,
    )

    shell.ft_rho_confirm_button = pn.widgets.Button(
        name="Confirm",
        button_type="primary",
        sizing_mode="fixed",
        width=120,
        height=48,
        visible=False,
    )
    shell.ft_rho_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=48,
        visible=False,
    )

    shell.ft_rho_confirm_selection_panel = pn.Column(
        pn.Row(
            pn.Column(
                pn.pane.Markdown("**G(R) Lorch**", margin=(0, 0, 0, 0), styles={"text-align": "center"}, sizing_mode="stretch_width"),
                shell.ft_rho_choice_lorch,
                shell.ft_rho_custom_lorch,
                sizing_mode="fixed",
                width=320,
                styles={"gap": "8px", "align-items": "center"},
            ),
            pn.Column(
                pn.pane.Markdown("**G(R) No Lorch**", margin=(0, 0, 0, 0), styles={"text-align": "center"}, sizing_mode="stretch_width"),
                shell.ft_rho_choice_no_lorch,
                shell.ft_rho_custom_no_lorch,
                sizing_mode="fixed",
                width=320,
                styles={"gap": "8px", "align-items": "center"},
            ),
            sizing_mode="fixed",
            width=660,
            styles={"gap": "20px", "align-items": "flex-start"},
        ),
        pn.Spacer(height=10),
        pn.Row(
            shell.ft_rho_confirm_button,
            shell.ft_rho_cancel_button,
            sizing_mode="stretch_width",
            styles={"gap": "12px", "justify-content": "center"},
        ),
        visible=False,
        sizing_mode="fixed",
        width=660,
        margin=(0, 0, 0, 0),
        styles={"gap": "10px"},
    )

    shell.ft_rho_run_fit_button = pn.widgets.Button(
        name="Run Fit",
        button_type="primary",
        sizing_mode="fixed",
        width=110,
        height=40,
        disabled=True,
    )

    shell.self_lowq_status = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_alert = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_lowq_selection_mode = pn.widgets.RadioButtonGroup(
        name="",
        options={
            "Percentile band": "percentile_band",
            "Manual window": "manual_window",
        },
        value="manual_window",
        button_type="light",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_use_sliders = pn.widgets.Toggle(
        name="Use sliders",
        value=True,
        button_type="light",
        sizing_mode="fixed",
        width=140,
        visible=False,
    )

    shell.self_lowq_q_tail_low = pn.widgets.FloatInput(
        name="Q start",
        value=0.45,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_q_tail_high = pn.widgets.FloatInput(
        name="Q end",
        value=2.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_min_percentile = pn.widgets.IntInput(
        name="Lower percentile",
        value=0,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_max_percentile = pn.widgets.IntInput(
        name="Upper percentile",
        value=95,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_lowq_q_min = pn.widgets.FloatInput(
        name="Q min",
        value=0.45,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_q_max = pn.widgets.FloatInput(
        name="Q max",
        value=2.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_y_min = pn.widgets.FloatInput(
        name="Intensity min",
        value=0.0,
        step=0.01,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_lowq_y_max = pn.widgets.FloatInput(
        name="Intensity max",
        value=1.5,
        step=0.01,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_lowq_redesign_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.self_lowq_redesign_switch_input_mode = pn.widgets.Button(
        name="Switch Input Mode",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.self_lowq_redesign_switch_method = pn.widgets.Button(
        name="Switch Method",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.self_lowq_extrapolate_button = pn.widgets.Button(
        name="Extrapolate",
        button_type="success",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
        disabled=True,
    )
    shell.self_lowq_redesign_mode_chips = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    shell.self_lowq_redesign_window_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    # Match the Normalization button bar behavior:
    # - left button flush with plot start
    # - right button flush with plot end
    # - middle button centered
    # Achieved by distributing the remaining horizontal space evenly.
    shell.self_lowq_redesign_top_controls = pn.Row(
        shell.self_lowq_redesign_switch_input_mode,
        shell.self_lowq_redesign_switch_method,
        shell.self_lowq_extrapolate_button,
        sizing_mode="fixed",
        width=800,
        margin=(0, 0, 0, 0),
        styles={
            "align-items": "center",
            "justify-content": "space-between",
            "gap": "0px",
            "padding": "0px",
            "box-sizing": "border-box",
        },
        align="center",
    )

    _fit_data_numeric_label_styles = {
        "color": "rgba(15, 23, 42, 0.95)",
        "font-family": "inherit",
        "font-size": "0.86rem",
        "font-weight": "700",
        "line-height": "1.1",
    }

    shell.self_lowq_redesign_q_start_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_lowq_q_min.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.self_lowq_redesign_q_end_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_lowq_q_max.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.self_lowq_redesign_q_input_row = pn.Row(
        pn.Row(
            pn.pane.HTML("Q start:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.self_lowq_redesign_q_start_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        pn.Spacer(),
        pn.Row(
            pn.pane.HTML("Q end:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.self_lowq_redesign_q_end_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        sizing_mode="fixed",
        width=600,
        margin=(0, 0, 0, 0),
        styles={"align-items": "center"},
        visible=False,
    )

    shell.self_lowq_redesign_q_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.self_lowq_q_min.value),
            float(shell.self_lowq_q_max.value),
        ],
        start=0.0,
        end=25.0,
        step=0.05,
        orientation="horizontal",
        label_display="flex",
        lower_label="Q start",
        upper_label="Q end",
        sizing_mode="fixed",
        width=600,
        height=58,
        visible=False,
    )

    shell.self_lowq_redesign_vertical_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.self_lowq_y_min.value),
            float(shell.self_lowq_y_max.value),
        ],
        start=0.0,
        end=2.0,
        step=0.01,
        orientation="vertical",
        sizing_mode="fixed",
        width=72,
        height=394,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.self_lowq_redesign_vertical_upper_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.self_lowq_redesign_vertical_upper_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_lowq_y_max.value),
        step=0.01,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.self_lowq_redesign_vertical_lower_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.self_lowq_redesign_vertical_lower_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_lowq_y_min.value),
        step=0.01,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )

    shell.self_lowq_redesign_vertical_axis_controls = pn.Row(
        pn.pane.HTML(
            """
            <div style="
                height: 450px;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <div style="
                    transform: rotate(-90deg);
                    white-space: nowrap;
                    font-size: 0.84rem;
                    font-weight: 700;
                letter-spacing: 0.02em;
                text-transform: uppercase;
                color: rgba(71, 85, 105, 0.86);
            font-size: 0.78rem;
            ">Intensity filter</div>
            </div>
            """,
            sizing_mode="fixed",
            width=26,
            height=450,
            margin=(0, 0, 0, 0),
        ),
        pn.Column(
            sizing_mode="fixed",
            width=154,
            height=450,
            styles={"align-items": "center"},
            margin=(0, 0, 0, 0),
            objects=[
                shell.self_lowq_redesign_vertical_upper_value,
                shell.self_lowq_redesign_vertical_upper_input,
                shell.self_lowq_redesign_vertical_range_slider,
                shell.self_lowq_redesign_vertical_lower_value,
                shell.self_lowq_redesign_vertical_lower_input,
            ],
        ),
        sizing_mode="fixed",
        width=206,
        height=450,
        styles={
            "align-items": "center",
            "box-sizing": "border-box",
            "gap": "4px",
            "padding": "0px",
        },
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--vertical",
        ],
        visible=False,
    )

    shell.self_lowq_redesign_horizontal_axis_controls = pn.Column(
        pn.pane.Markdown(
            "Q filter",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-axis-title"],
        ),
        shell.self_lowq_redesign_q_input_row,
        pn.Row(
            shell.self_lowq_redesign_q_range_slider,
            sizing_mode="fixed",
            width=600,
            styles={"gap": "0px"},
        ),
        sizing_mode="fixed",
        width=600,
        visible=False,
        margin=(0, 0, 0, 0),
        styles={"box-sizing": "border-box", "padding": "0px"},
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--horizontal",
        ],
    )

    shell.self_lowq_view_switch = pn.widgets.Switch(
        name="",
        value=False,
        sizing_mode="fixed",
        width=54,
        height=32,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-switch-view"],
        stylesheets=shell.normalization_vanadium_self_fit_preview_view_switch.stylesheets
        if hasattr(shell, "normalization_vanadium_self_fit_preview_view_switch")
        else [],
    )
    shell.self_lowq_view_selector = pn.Row(
        pn.pane.Markdown(
            "Switch View",
            margin=(0, 10, 0, 0),
            align="center",
            styles={
                "font-size": "0.86rem",
                "font-weight": "700",
                "color": "rgba(15, 23, 42, 0.82)",
            },
        ),
        pn.Column(
            shell.self_lowq_view_switch,
            margin=(45, 0, 0, 0),
            align="center",
            sizing_mode="fixed",
        ),
        sizing_mode="stretch_width",
        height=34,
        styles={
            "display": "flex",
            "align-items": "center",
            "justify-content": "flex-end",
        },
    )

    # ------------------------------
    # Self scattering (Data selection)
    # ------------------------------
    shell.self_data_selection_status = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_alert = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_data_selection_selection_mode = pn.widgets.RadioButtonGroup(
        name="",
        options={
            "Percentile band": "percentile_band",
            "Manual window": "manual_window",
        },
        value="percentile_band",
        button_type="light",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_use_sliders = pn.widgets.Toggle(
        name="Use sliders",
        value=True,
        button_type="light",
        sizing_mode="fixed",
        width=140,
        visible=False,
    )

    shell.self_data_selection_q_tail_low = pn.widgets.FloatInput(
        name="Q start",
        value=4.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_q_tail_high = pn.widgets.FloatInput(
        name="Q end",
        value=20.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_min_percentile = pn.widgets.IntInput(
        name="Lower percentile",
        value=0,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_max_percentile = pn.widgets.IntInput(
        name="Upper percentile",
        value=95,
        start=0,
        end=100,
        step=1,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_data_selection_q_min = pn.widgets.FloatInput(
        name="Q min",
        value=0.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_q_max = pn.widgets.FloatInput(
        name="Q max",
        value=25.0,
        step=0.05,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_y_min = pn.widgets.FloatInput(
        name="Intensity min",
        value=0.0,
        step=0.01,
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_data_selection_y_max = pn.widgets.FloatInput(
        name="Intensity max",
        value=6.0,
        step=0.01,
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_data_selection_redesign_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.self_data_selection_redesign_switch_input_mode = pn.widgets.Button(
        name="Switch Input Mode",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.self_data_selection_redesign_switch_method = pn.widgets.Button(
        name="Switch Method",
        button_type="primary",
        sizing_mode="fixed",
        width=190,
        height=62,
        margin=(0, 0, 0, 0),
    )
    shell.self_data_selection_redesign_mode_chips = pn.pane.HTML(
        "",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
    )

    shell.self_data_selection_redesign_window_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    shell.self_data_selection_redesign_top_controls = pn.Row(
        shell.self_data_selection_redesign_switch_input_mode,
        shell.self_data_selection_redesign_switch_method,
        sizing_mode="fixed",
        width=800,
        # Match Normalization → Select Fitting Data button bar positioning exactly.
        margin=(0, 0, 0, -250),
        styles={
            "align-items": "center",
            "justify-content": "center",
            "gap": "14px",
        },
        align="center",
    )

    shell.self_data_selection_redesign_q_start_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_data_selection_q_tail_low.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.self_data_selection_redesign_q_end_input = pn.widgets.FloatInput(
        name="",
        value=float(shell.self_data_selection_q_tail_high.value),
        step=0.05,
        sizing_mode="fixed",
        width=110,
        height=32,
        margin=(0, 0, 0, 0),
    )
    shell.self_data_selection_redesign_q_input_row = pn.Row(
        pn.Row(
            pn.pane.HTML("Q start:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.self_data_selection_redesign_q_start_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        pn.Spacer(),
        pn.Row(
            pn.pane.HTML("Q end:", styles=_fit_data_numeric_label_styles, margin=(0, 6, 0, 0)),
            shell.self_data_selection_redesign_q_end_input,
            sizing_mode="fixed",
            margin=(0, 0, 0, 0),
            styles={"align-items": "center"},
        ),
        sizing_mode="fixed",
        width=600,
        margin=(0, 0, 0, 0),
        styles={"align-items": "center"},
        visible=False,
    )

    shell.self_data_selection_redesign_q_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.self_data_selection_q_tail_low.value),
            float(shell.self_data_selection_q_tail_high.value),
        ],
        start=0.0,
        end=25.0,
        step=0.05,
        orientation="horizontal",
        label_display="flex",
        lower_label="Q start",
        upper_label="Q end",
        sizing_mode="fixed",
        width=600,
        height=58,
        visible=False,
    )

    shell.self_data_selection_redesign_vertical_range_slider = ToscanaRangeSlider(
        value=[
            float(shell.self_data_selection_min_percentile.value),
            float(shell.self_data_selection_max_percentile.value),
        ],
        start=0,
        end=100,
        step=1,
        orientation="vertical",
        sizing_mode="fixed",
        width=72,
        height=394,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.self_data_selection_redesign_vertical_upper_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.self_data_selection_redesign_vertical_upper_input = pn.widgets.FloatInput(
        name="",
        value=0.0,
        step=1.0,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )
    shell.self_data_selection_redesign_vertical_lower_value = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=154,
        height=28,
        margin=(0, 0, 0, 0),
        styles={
            "color": "rgba(15, 23, 42, 0.95)",
            "font-family": "inherit",
            "font-size": "0.86rem",
            "font-weight": "700",
            "line-height": "1.1",
            "text-align": "center",
        },
    )
    shell.self_data_selection_redesign_vertical_lower_input = pn.widgets.FloatInput(
        name="",
        value=0.0,
        step=1.0,
        sizing_mode="fixed",
        width=154,
        height=32,
        margin=(0, 0, 0, 0),
        visible=False,
    )

    shell.self_data_selection_redesign_vertical_axis_controls = pn.Row(
        pn.pane.HTML(
            """
            <div style="
                height: 450px;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <div style="
                    transform: rotate(-90deg);
                    white-space: nowrap;
                    font-size: 0.84rem;
                    font-weight: 700;
                letter-spacing: 0.02em;
                text-transform: uppercase;
                color: rgba(71, 85, 105, 0.86);
            font-size: 0.78rem;
            ">Intensity filter</div>
            </div>
            """,
            sizing_mode="fixed",
            width=26,
            height=450,
            margin=(0, 0, 0, 0),
        ),
        pn.Column(
            sizing_mode="fixed",
            width=154,
            height=450,
            styles={"align-items": "center"},
            margin=(0, 0, 0, 0),
            objects=[
                shell.self_data_selection_redesign_vertical_upper_value,
                shell.self_data_selection_redesign_vertical_upper_input,
                shell.self_data_selection_redesign_vertical_range_slider,
                shell.self_data_selection_redesign_vertical_lower_value,
                shell.self_data_selection_redesign_vertical_lower_input,
            ],
        ),
        sizing_mode="fixed",
        width=206,
        height=450,
        styles={
            "align-items": "center",
            "box-sizing": "border-box",
            "gap": "4px",
            "padding": "0px",
        },
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--vertical",
        ],
        visible=False,
    )

    shell.self_data_selection_redesign_horizontal_axis_controls = pn.Column(
        pn.pane.Markdown(
            "Q filter",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-axis-title"],
        ),
        shell.self_data_selection_redesign_q_input_row,
        pn.Row(
            shell.self_data_selection_redesign_q_range_slider,
            sizing_mode="fixed",
            width=600,
            styles={"gap": "0px"},
        ),
        sizing_mode="fixed",
        width=600,
        visible=False,
        margin=(0, 0, 0, 0),
        styles={"box-sizing": "border-box", "padding": "0px"},
        css_classes=[
            "toscana-normalization-axis-controls",
            "toscana-normalization-axis-controls--horizontal",
        ],
    )

    # ------------------------------
    # Self scattering (Fit model)
    # ------------------------------
    shell.self_fit_model_selector = pn.widgets.Select(
        name="",
        options={
            "Sigmoidal + Polynomial Model": "vanaQdep",
            "Polynomial Model (Fourth Degree Max)": "polyQ4",
            "Lorentzian + Gaussian Model": "LorGau",
        },
        value="vanaQdep",
        sizing_mode="fixed",
        width=440,
    )
    shell.self_fit_model_info_hover = pn.widgets.TooltipIcon(
        value=(
            "<div style=\"max-width: 320px; line-height: 1.4; white-space: normal; "
            "overflow-wrap: anywhere; word-break: break-word;\">"
            "Select Data Fitting Model"
            "</div>"
        ),
        sizing_mode="fixed",
        width=34,
        height=34,
        align="center",
        margin=(12, 0, 0, 0),
    )

    shell.self_fit_params_status = pn.pane.Markdown(
        "**Status:** Select a context and run **Sample Extrapolation to Low Q** to enable fitting.",
        sizing_mode="stretch_width",
    )
    shell.self_fit_params_alert = pn.pane.Alert(
        "",
        alert_type="secondary",
        sizing_mode="stretch_width",
        visible=False,
    )

    shell.self_fit_params_suggest_button = pn.widgets.Button(
        name="Suggest Initial Guess",
        button_type="light",
        sizing_mode="fixed",
        width=240,
        height=40,
        disabled=True,
        css_classes=["toscana-btn-suggest"],
        # Bokeh 3 widgets render in Shadow DOM; global CSS in assets/toscana.css
        # cannot reliably style the internal <button>. Use widget stylesheets.
        stylesheets=[
            """
            :host .bk-btn,
            :host(.bk-btn) {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
              padding-left: 16px;
              padding-right: 16px;
            }

            :host .bk-btn:hover {
              filter: brightness(1.04);
            }

            :host .bk-btn:focus,
            :host .bk-btn:active {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
            }

            :host(.bk-disabled) .bk-btn,
            :host .bk-btn:disabled,
            :host .bk-btn[disabled] {
              background: #5a5daa;
              border-color: #5a5daa;
              color: #ffffff;
              opacity: 0.55;
            }
            """
        ],
    )
    shell.self_fit_params_run_button = pn.widgets.Button(
        name="Run Fit",
        button_type="primary",
        sizing_mode="fixed",
        width=110,
        height=40,
        disabled=True,
    )

    shell.self_fit_params_bounds_toggle = pn.widgets.Toggle(
        name="Advanced bounds",
        value=False,
        button_type="light",
        sizing_mode="stretch_width",
        height=36,
    )

    shell.self_fit_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.self_static_structure_factor_plot_pane = pn.pane.Plotly(
        None,
        sizing_mode="fixed",
        config={"responsive": False},
        width=800,
        height=600,
    )

    shell.self_static_structure_factor_summary_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    shell.self_export_folder_input = pn.widgets.TextInput(
        name="Export folder",
        value="self_scattering/",
        placeholder="self_scattering/",
        sizing_mode="stretch_width",
    )
    shell.self_export_button = pn.widgets.Button(
        name="Export Data",
        button_type="primary",
        sizing_mode="fixed",
        width=180,
        height=48,
        disabled=True,
    )
    shell.self_export_info_hover = pn.widgets.TooltipIcon(
        value="",
        sizing_mode="fixed",
        width=36,
        height=36,
        margin=(0, 0, 0, 0),
    )
    shell.self_export_prompt = pn.pane.Alert(
        "",
        alert_type="warning",
        sizing_mode="stretch_width",
        visible=False,
    )
    shell.self_export_confirm_button = pn.widgets.Button(
        name="Export",
        button_type="success",
        sizing_mode="fixed",
        width=120,
        height=40,
        disabled=False,
    )
    shell.self_export_cancel_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        sizing_mode="fixed",
        width=120,
        height=40,
        disabled=False,
    )
    shell.self_export_prompt_card = pn.Card(
        shell.self_export_prompt,
        pn.Row(
            shell.self_export_confirm_button,
            shell.self_export_cancel_button,
            sizing_mode="stretch_width",
            styles={"justify-content": "flex-end", "gap": "10px"},
            margin=(8, 0, 0, 0),
        ),
        pn.Spacer(height=6),
        title="Confirm Export",
        sizing_mode="stretch_width",
        visible=False,
        css_classes=["toscana-export-prompt-card"],
    )
    shell.self_export_card = pn.Card(
        pn.Column(
            shell.self_export_folder_input,
            pn.Row(
                shell.self_export_button,
                shell.self_export_info_hover,
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        ),
        shell.self_export_prompt_card,
        title="Export Data",
        sizing_mode="stretch_width",
        css_classes=["toscana-overflow-visible"],
        styles={"overflow": "visible", "margin-bottom": "180px"},
        visible=True,
    )

    shell.self_fit_result_table = pn.pane.HTML(
        "",
        sizing_mode="fixed",
        width=320,
        margin=(0, 0, 0, 0),
        css_classes=["toscana-fit-window-table-host"],
    )

    def _self_fit_fix_toggle(default: bool = False) -> pn.widgets.Checkbox:
        return pn.widgets.Checkbox(
            name="Fix",
            value=bool(default),
            sizing_mode="fixed",
            width=58,
            height=32,
            margin=(0, 0, 0, 0),
            css_classes=["toscana-fit-fix-toggle"],
        )

    shell.self_fit_params_vana_a0_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_a1_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_a2_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_A_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_lowQ_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_Q0_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_vana_dQ_fixed = _self_fit_fix_toggle(False)

    shell.self_fit_params_poly_a0_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_poly_a1_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_poly_a2_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_poly_a3_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_poly_a4_fixed = _self_fit_fix_toggle(False)

    shell.self_fit_params_lorgau_f0_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_lorgau_eta_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_lorgau_sigma_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_lorgau_gamma_fixed = _self_fit_fix_toggle(False)
    shell.self_fit_params_lorgau_bckg_fixed = _self_fit_fix_toggle(False)

    # Tooltips + value widgets.
    shell.self_fit_params_vana_a0_info = _fit_param_tooltip(
        "Polynomial constant term. Defaults to 1 (no scaling)."
    )
    shell.self_fit_params_vana_a1_info = _fit_param_tooltip(
        "Polynomial linear coefficient in Q. Defaults to 0."
    )
    shell.self_fit_params_vana_a2_info = _fit_param_tooltip(
        "Polynomial quadratic coefficient in Q. Defaults to 0."
    )
    shell.self_fit_params_vana_A_info = _fit_param_tooltip(
        "Mass number used by the sigmoidal+polynomial model. Default is 51."
    )
    shell.self_fit_params_vana_lowQ_info = _fit_param_tooltip(
        "Low-Q asymptote of the sigmoidal model as Q -> 0."
    )
    shell.self_fit_params_vana_Q0_info = _fit_param_tooltip(
        "Inflection point of the sigmoidal transition in Q."
    )
    shell.self_fit_params_vana_dQ_info = _fit_param_tooltip(
        "Transition width of the sigmoidal model (larger = smoother)."
    )

    shell.self_fit_params_poly_a0_info = _fit_param_tooltip("Polynomial constant term.")
    shell.self_fit_params_poly_a1_info = _fit_param_tooltip("Polynomial linear coefficient in Q.")
    shell.self_fit_params_poly_a2_info = _fit_param_tooltip("Polynomial quadratic coefficient in Q.")
    shell.self_fit_params_poly_a3_info = _fit_param_tooltip("Polynomial cubic coefficient in Q.")
    shell.self_fit_params_poly_a4_info = _fit_param_tooltip("Polynomial quartic coefficient in Q.")

    shell.self_fit_params_lorgau_f0_info = _fit_param_tooltip("Overall multiplicative factor.")
    shell.self_fit_params_lorgau_eta_info = _fit_param_tooltip(
        "Gaussian weight in [0,1] (0 = pure Lorentzian, 1 = pure Gaussian)."
    )
    shell.self_fit_params_lorgau_sigma_info = _fit_param_tooltip("Gaussian width parameter (sigma).")
    shell.self_fit_params_lorgau_gamma_info = _fit_param_tooltip("Lorentzian width parameter (gamma).")
    shell.self_fit_params_lorgau_bckg_info = _fit_param_tooltip("Additive constant background offset.")

    # Values.
    shell.self_fit_params_vana_a0_value = _fit_float(1.0)
    shell.self_fit_params_vana_a1_value = _fit_float(0.0)
    shell.self_fit_params_vana_a2_value = _fit_float(0.0)
    shell.self_fit_params_vana_A_value = _fit_float(51.0)
    shell.self_fit_params_vana_lowQ_value = _fit_float(0.4)
    shell.self_fit_params_vana_Q0_value = _fit_float(7.4)
    shell.self_fit_params_vana_dQ_value = _fit_float(2.4)

    shell.self_fit_params_poly_a0_value = _fit_float(0.0)
    shell.self_fit_params_poly_a1_value = _fit_float(0.0)
    shell.self_fit_params_poly_a2_value = _fit_float(0.0)
    shell.self_fit_params_poly_a3_value = _fit_float(0.0)
    shell.self_fit_params_poly_a4_value = _fit_float(0.0)

    shell.self_fit_params_lorgau_f0_value = _fit_float(1.0)
    shell.self_fit_params_lorgau_eta_value = _fit_float(0.5)
    shell.self_fit_params_lorgau_sigma_value = _fit_float(2.0)
    shell.self_fit_params_lorgau_gamma_value = _fit_float(2.0)
    shell.self_fit_params_lorgau_bckg_value = _fit_float(0.0)

    # Bounds.
    self_bound_wide = 1e6
    def _b(v: float) -> pn.widgets.LiteralInput:
        return _fit_bound(v)

    shell.self_fit_params_vana_a0_min = _b(-self_bound_wide)
    shell.self_fit_params_vana_a0_max = _b(self_bound_wide)
    shell.self_fit_params_vana_a1_min = _b(-self_bound_wide)
    shell.self_fit_params_vana_a1_max = _b(self_bound_wide)
    shell.self_fit_params_vana_a2_min = _b(-self_bound_wide)
    shell.self_fit_params_vana_a2_max = _b(self_bound_wide)
    shell.self_fit_params_vana_A_min = _b(1.0)
    shell.self_fit_params_vana_A_max = _b(300.0)
    shell.self_fit_params_vana_lowQ_min = _b(0.0)
    shell.self_fit_params_vana_lowQ_max = _b(self_bound_wide)
    shell.self_fit_params_vana_Q0_min = _b(0.0)
    shell.self_fit_params_vana_Q0_max = _b(25.0)
    shell.self_fit_params_vana_dQ_min = _b(1e-3)
    shell.self_fit_params_vana_dQ_max = _b(25.0)

    shell.self_fit_params_poly_a0_min = _b(-self_bound_wide)
    shell.self_fit_params_poly_a0_max = _b(self_bound_wide)
    shell.self_fit_params_poly_a1_min = _b(-self_bound_wide)
    shell.self_fit_params_poly_a1_max = _b(self_bound_wide)
    shell.self_fit_params_poly_a2_min = _b(-self_bound_wide)
    shell.self_fit_params_poly_a2_max = _b(self_bound_wide)
    shell.self_fit_params_poly_a3_min = _b(-self_bound_wide)
    shell.self_fit_params_poly_a3_max = _b(self_bound_wide)
    shell.self_fit_params_poly_a4_min = _b(-self_bound_wide)
    shell.self_fit_params_poly_a4_max = _b(self_bound_wide)

    shell.self_fit_params_lorgau_f0_min = _b(-self_bound_wide)
    shell.self_fit_params_lorgau_f0_max = _b(self_bound_wide)
    shell.self_fit_params_lorgau_eta_min = _b(0.0)
    shell.self_fit_params_lorgau_eta_max = _b(1.0)
    shell.self_fit_params_lorgau_sigma_min = _b(1e-6)
    shell.self_fit_params_lorgau_sigma_max = _b(self_bound_wide)
    shell.self_fit_params_lorgau_gamma_min = _b(1e-6)
    shell.self_fit_params_lorgau_gamma_max = _b(self_bound_wide)
    shell.self_fit_params_lorgau_bckg_min = _b(-self_bound_wide)
    shell.self_fit_params_lorgau_bckg_max = _b(self_bound_wide)

    # Core parameter sections (per model); only one is visible at a time.
    shell.self_fit_params_vana_section = pn.Column(
        pn.pane.Markdown(
            "Parameters",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        _fit_param_row(
            "`a0`",
            shell.self_fit_params_vana_a0_info,
            shell.self_fit_params_vana_a0_value,
            adornment=shell.self_fit_params_vana_a0_fixed,
        ),
        _fit_param_row(
            "`a1`",
            shell.self_fit_params_vana_a1_info,
            shell.self_fit_params_vana_a1_value,
            adornment=shell.self_fit_params_vana_a1_fixed,
        ),
        _fit_param_row(
            "`a2`",
            shell.self_fit_params_vana_a2_info,
            shell.self_fit_params_vana_a2_value,
            adornment=shell.self_fit_params_vana_a2_fixed,
        ),
        _fit_param_row(
            "`A`",
            shell.self_fit_params_vana_A_info,
            shell.self_fit_params_vana_A_value,
            adornment=shell.self_fit_params_vana_A_fixed,
        ),
        _fit_param_row(
            "`lowQ`",
            shell.self_fit_params_vana_lowQ_info,
            shell.self_fit_params_vana_lowQ_value,
            adornment=shell.self_fit_params_vana_lowQ_fixed,
        ),
        _fit_param_row(
            "`Q0`",
            shell.self_fit_params_vana_Q0_info,
            shell.self_fit_params_vana_Q0_value,
            adornment=shell.self_fit_params_vana_Q0_fixed,
        ),
        _fit_param_row(
            "`dQ`",
            shell.self_fit_params_vana_dQ_info,
            shell.self_fit_params_vana_dQ_value,
            adornment=shell.self_fit_params_vana_dQ_fixed,
        ),
        sizing_mode="stretch_width",
        styles=_fit_section_box_styles,
        css_classes=["toscana-normalization-fit-section-card"],
        visible=True,
    )

    shell.self_fit_params_poly_section = pn.Column(
        pn.pane.Markdown(
            "Parameters",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        _fit_param_row(
            "`a0`",
            shell.self_fit_params_poly_a0_info,
            shell.self_fit_params_poly_a0_value,
            adornment=shell.self_fit_params_poly_a0_fixed,
        ),
        _fit_param_row(
            "`a1`",
            shell.self_fit_params_poly_a1_info,
            shell.self_fit_params_poly_a1_value,
            adornment=shell.self_fit_params_poly_a1_fixed,
        ),
        _fit_param_row(
            "`a2`",
            shell.self_fit_params_poly_a2_info,
            shell.self_fit_params_poly_a2_value,
            adornment=shell.self_fit_params_poly_a2_fixed,
        ),
        _fit_param_row(
            "`a3`",
            shell.self_fit_params_poly_a3_info,
            shell.self_fit_params_poly_a3_value,
            adornment=shell.self_fit_params_poly_a3_fixed,
        ),
        _fit_param_row(
            "`a4`",
            shell.self_fit_params_poly_a4_info,
            shell.self_fit_params_poly_a4_value,
            adornment=shell.self_fit_params_poly_a4_fixed,
        ),
        sizing_mode="stretch_width",
        styles=_fit_section_box_styles,
        css_classes=["toscana-normalization-fit-section-card"],
        visible=False,
    )

    shell.self_fit_params_lorgau_section = pn.Column(
        pn.pane.Markdown(
            "Parameters",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        _fit_param_row(
            "`f0`",
            shell.self_fit_params_lorgau_f0_info,
            shell.self_fit_params_lorgau_f0_value,
            adornment=shell.self_fit_params_lorgau_f0_fixed,
        ),
        _fit_param_row(
            "`eta`",
            shell.self_fit_params_lorgau_eta_info,
            shell.self_fit_params_lorgau_eta_value,
            adornment=shell.self_fit_params_lorgau_eta_fixed,
        ),
        _fit_param_row(
            "`sigma`",
            shell.self_fit_params_lorgau_sigma_info,
            shell.self_fit_params_lorgau_sigma_value,
            adornment=shell.self_fit_params_lorgau_sigma_fixed,
        ),
        _fit_param_row(
            "`gamma`",
            shell.self_fit_params_lorgau_gamma_info,
            shell.self_fit_params_lorgau_gamma_value,
            adornment=shell.self_fit_params_lorgau_gamma_fixed,
        ),
        _fit_param_row(
            "`bckg`",
            shell.self_fit_params_lorgau_bckg_info,
            shell.self_fit_params_lorgau_bckg_value,
            adornment=shell.self_fit_params_lorgau_bckg_fixed,
        ),
        sizing_mode="stretch_width",
        styles=_fit_section_box_styles,
        css_classes=["toscana-normalization-fit-section-card"],
        visible=False,
    )

    def _bounds_grid(labels: list[str], min_widgets: list[object], max_widgets: list[object]) -> pn.GridBox:
        header_margin = (-9, 0, 0, 0)
        return pn.GridBox(
            pn.pane.Markdown("**Parameter**", margin=header_margin),
            *[pn.pane.Markdown(label, margin=(-8, 0, 0, 0)) for label in labels],
            pn.pane.Markdown("**Min**", margin=header_margin),
            *min_widgets,
            pn.pane.Markdown("**Max**", margin=header_margin),
            *max_widgets,
            ncols=1 + len(labels),
            sizing_mode="stretch_width",
            css_classes=[
                "toscana-normalization-fit-bounds-grid",
                "toscana-normalization-fit-bounds-grid--horizontal",
            ],
        )

    shell.self_fit_params_vana_bounds_grid = _bounds_grid(
        ["a0", "a1", "a2", "A", "lowQ", "Q0", "dQ"],
        [
            shell.self_fit_params_vana_a0_min,
            shell.self_fit_params_vana_a1_min,
            shell.self_fit_params_vana_a2_min,
            shell.self_fit_params_vana_A_min,
            shell.self_fit_params_vana_lowQ_min,
            shell.self_fit_params_vana_Q0_min,
            shell.self_fit_params_vana_dQ_min,
        ],
        [
            shell.self_fit_params_vana_a0_max,
            shell.self_fit_params_vana_a1_max,
            shell.self_fit_params_vana_a2_max,
            shell.self_fit_params_vana_A_max,
            shell.self_fit_params_vana_lowQ_max,
            shell.self_fit_params_vana_Q0_max,
            shell.self_fit_params_vana_dQ_max,
        ],
    )
    shell.self_fit_params_poly_bounds_grid = _bounds_grid(
        ["a0", "a1", "a2", "a3", "a4"],
        [
            shell.self_fit_params_poly_a0_min,
            shell.self_fit_params_poly_a1_min,
            shell.self_fit_params_poly_a2_min,
            shell.self_fit_params_poly_a3_min,
            shell.self_fit_params_poly_a4_min,
        ],
        [
            shell.self_fit_params_poly_a0_max,
            shell.self_fit_params_poly_a1_max,
            shell.self_fit_params_poly_a2_max,
            shell.self_fit_params_poly_a3_max,
            shell.self_fit_params_poly_a4_max,
        ],
    )
    shell.self_fit_params_lorgau_bounds_grid = _bounds_grid(
        ["f0", "eta", "sigma", "gamma", "bckg"],
        [
            shell.self_fit_params_lorgau_f0_min,
            shell.self_fit_params_lorgau_eta_min,
            shell.self_fit_params_lorgau_sigma_min,
            shell.self_fit_params_lorgau_gamma_min,
            shell.self_fit_params_lorgau_bckg_min,
        ],
        [
            shell.self_fit_params_lorgau_f0_max,
            shell.self_fit_params_lorgau_eta_max,
            shell.self_fit_params_lorgau_sigma_max,
            shell.self_fit_params_lorgau_gamma_max,
            shell.self_fit_params_lorgau_bckg_max,
        ],
    )

    shell.self_fit_params_bounds_card = pn.Column(
        pn.pane.Markdown(
            "Advanced bounds",
            sizing_mode="stretch_width",
            css_classes=["toscana-normalization-fit-section-title"],
        ),
        pn.pane.Markdown(
            "Use this only when the suggested or current parameter range needs manual tightening.",
            sizing_mode="stretch_width",
        ),
        shell.self_fit_params_vana_bounds_grid,
        shell.self_fit_params_poly_bounds_grid,
        shell.self_fit_params_lorgau_bounds_grid,
        sizing_mode="stretch_width",
        visible=False,
        margin=(12, 0, 0, 0),
        styles={**_fit_section_box_styles, "overflow-x": "auto"},
        css_classes=["toscana-normalization-fit-bounds-card"],
    )

    shell.self_fit_params_poly_bounds_grid.visible = False
    shell.self_fit_params_lorgau_bounds_grid.visible = False

    shell._pending_numors_import_path: Path | None = None
    shell.recent_projects_column = pn.Column(sizing_mode="stretch_width")
    shell._selected_recent_project_file: str | None = None
    shell.save_and_continue_button = pn.widgets.Button(
        name="Save and Continue",
        button_type="primary",
        width=180,
        height=48,
    )
    shell.discard_and_continue_button = pn.widgets.Button(
        name="Discard and Continue",
        button_type="warning",
        width=190,
        height=48,
    )
    shell.cancel_navigation_button = pn.widgets.Button(
        name="Cancel",
        button_type="light",
        width=120,
        height=48,
    )

    try:
        area = pn.state.notifications
        if area is not None:
            area.max_notifications = 8
            area.position = "top-right"
    except Exception:
        pass
