from __future__ import annotations

import panel as pn

from toscana_gui.ui.run_block_viewer import (
    build_run_block_details_markdown,
    build_run_block_options,
    clamp_run_block_selection,
    create_run_block_plot_display,
    render_run_block_plot_display,
    summarize_run_blocks,
)


def build_run_history_section(shell) -> pn.Column:
    if shell.current_project_state is None or not shell.current_project_state.runs:
        return pn.Column(
            pn.pane.Markdown("No recorded runs yet.", sizing_mode="stretch_width"),
            sizing_mode="stretch_width",
        )

    cards: list[object] = []
    active_run_ids: set[str] = set()
    for record in shell.current_project_state.runs:
        active_run_ids.add(record.run_id)
        lines = [
            f"**Run ID:** {record.run_id}",
            f"**Workflow:** {record.workflow}",
            f"**Status:** {record.status}",
            f"**Started:** {record.started_at}",
        ]
        if record.finished_at:
            lines.append(f"**Finished:** {record.finished_at}")
        if record.summary:
            lines.append(f"**Summary:** {record.summary}")
        if record.error:
            lines.append(f"**Error:** {record.error}")
        if record.output_paths.stdout_file:
            lines.append(f"**stdout:** `{record.output_paths.stdout_file}`")
        if record.output_paths.logfile:
            lines.append(f"**logfile:** `{record.output_paths.logfile}`")
        if record.output_paths.generated_files:
            lines.append(f"**Generated files:** `{len(record.output_paths.generated_files)}`")
            lines.extend(
                f"**output:** `{generated_file}`"
                for generated_file in record.output_paths.generated_files
            )
        else:
            if record.output_paths.reg_file:
                lines.append(f"**reg:** `{record.output_paths.reg_file}`")
            if record.output_paths.adat_file:
                lines.append(f"**adat:** `{record.output_paths.adat_file}`")
            if record.output_paths.qdat_file:
                lines.append(f"**qdat:** `{record.output_paths.qdat_file}`")

        extra_sections: list[object] = []
        workflow_data = getattr(record, "workflow_data", None)
        run_blocks = workflow_data.get("run_blocks") if isinstance(workflow_data, dict) else None
        if record.workflow == "numors" and isinstance(run_blocks, list) and run_blocks:
            succeeded_blocks, failed_blocks, block_lines = summarize_run_blocks(run_blocks)
            lines.append(
                f"**Run blocks:** `{len(run_blocks)}` (succeeded: `{succeeded_blocks}`, failed: `{failed_blocks}`)"
            )

            viewer_entry = _get_or_create_run_history_viewer(shell, record.run_id)
            viewer_entry["run_blocks"] = run_blocks
            _refresh_run_history_viewer(viewer_entry)

            accordion = pn.Accordion(
                (
                    "run blocks",
                    pn.pane.Markdown("\n".join(block_lines), sizing_mode="stretch_width"),
                ),
                ("viewer", viewer_entry["viewer"]),
                active=[],
                sizing_mode="stretch_width",
            )
            extra_sections.append(accordion)

        cards.append(
            pn.Card(
                pn.pane.Markdown("\n".join(lines), sizing_mode="stretch_width"),
                *extra_sections,
                title=f"Run {record.run_id}",
                sizing_mode="stretch_width",
            )
        )

    _prune_run_history_viewers(shell, active_run_ids)
    return pn.Column(*cards, sizing_mode="stretch_width")


def _get_or_create_run_history_viewer(shell, run_id: str) -> dict[str, object]:
    cache = getattr(shell, "_run_history_block_viewers", None)
    if cache is None:
        shell._run_history_block_viewers = {}
        cache = shell._run_history_block_viewers

    viewer_entry = cache.get(run_id)
    if viewer_entry is not None:
        return viewer_entry

    details_pane = pn.pane.Markdown("", sizing_mode="stretch_width")
    plot_counter_pane = pn.pane.Markdown("", sizing_mode="stretch_width")
    plot_display = create_run_block_plot_display()

    block_select = pn.widgets.Select(
        name="Block",
        options={},
        value=0,
        sizing_mode="stretch_width",
    )
    prev_block = pn.widgets.Button(name="Prev Block", button_type="light", width=140)
    next_block = pn.widgets.Button(name="Next Block", button_type="light", width=140)
    prev_plot = pn.widgets.Button(name="Prev Plot", button_type="light", width=140)
    next_plot = pn.widgets.Button(name="Next Plot", button_type="light", width=140)

    viewer_entry = {
        "state": {"block_index": 0, "plot_index": 0},
        "run_blocks": [],
        "suspend_events": False,
        "details_pane": details_pane,
        "plot_counter_pane": plot_counter_pane,
        "plot_display": plot_display,
        "block_select": block_select,
        "prev_block": prev_block,
        "next_block": next_block,
        "prev_plot": prev_plot,
        "next_plot": next_plot,
    }

    def _set_block_index(value: int) -> None:
        viewer_entry["state"]["block_index"] = value
        viewer_entry["state"]["plot_index"] = 0
        _refresh_run_history_viewer(viewer_entry)

    def _on_prev_block(_event=None) -> None:
        _set_block_index(int(viewer_entry["state"]["block_index"]) - 1)

    def _on_next_block(_event=None) -> None:
        _set_block_index(int(viewer_entry["state"]["block_index"]) + 1)

    def _on_prev_plot(_event=None) -> None:
        viewer_entry["state"]["plot_index"] = max(0, int(viewer_entry["state"]["plot_index"]) - 1)
        _refresh_run_history_viewer(viewer_entry)

    def _on_next_plot(_event=None) -> None:
        viewer_entry["state"]["plot_index"] = int(viewer_entry["state"]["plot_index"]) + 1
        _refresh_run_history_viewer(viewer_entry)

    def _on_block_select(event) -> None:
        if viewer_entry["suspend_events"] or event.new is None:
            return
        try:
            _set_block_index(int(event.new))
        except (TypeError, ValueError):
            return

    prev_block.on_click(_on_prev_block)
    next_block.on_click(_on_next_block)
    prev_plot.on_click(_on_prev_plot)
    next_plot.on_click(_on_next_plot)
    block_select.param.watch(_on_block_select, "value")

    viewer_entry["viewer"] = pn.Column(
        block_select,
        pn.Row(prev_block, next_block, sizing_mode="stretch_width"),
        details_pane,
        pn.Row(prev_plot, next_plot, plot_counter_pane, sizing_mode="stretch_width"),
        plot_display.container,
        sizing_mode="stretch_width",
    )
    cache[run_id] = viewer_entry
    return viewer_entry


def _refresh_run_history_viewer(viewer_entry: dict[str, object]) -> None:
    run_blocks = viewer_entry["run_blocks"]
    if not isinstance(run_blocks, list) or not run_blocks:
        return

    viewer_state = viewer_entry["state"]
    block_index, plot_index, block, plot_files = clamp_run_block_selection(
        run_blocks,
        int(viewer_state["block_index"]),
        int(viewer_state["plot_index"]),
    )
    viewer_state["block_index"] = block_index
    viewer_state["plot_index"] = plot_index

    options = build_run_block_options(run_blocks)
    viewer_entry["suspend_events"] = True
    viewer_entry["block_select"].options = options
    viewer_entry["block_select"].value = block_index
    viewer_entry["suspend_events"] = False

    viewer_entry["details_pane"].object = build_run_block_details_markdown(
        run_blocks=run_blocks,
        block_index=block_index,
        block=block,
        plot_files=plot_files,
    )
    viewer_entry["prev_block"].disabled = block_index <= 0
    viewer_entry["next_block"].disabled = block_index >= len(run_blocks) - 1
    viewer_entry["prev_plot"].disabled = not plot_files or plot_index <= 0
    viewer_entry["next_plot"].disabled = not plot_files or plot_index >= len(plot_files) - 1
    viewer_entry["plot_counter_pane"].object = render_run_block_plot_display(
        viewer_entry["plot_display"],
        plot_files=plot_files,
        plot_index=plot_index,
        empty_message="No per-block plots recorded for this run.",
    )


def _prune_run_history_viewers(shell, active_run_ids: set[str]) -> None:
    cache = getattr(shell, "_run_history_block_viewers", None)
    if cache is None:
        return
    shell._run_history_block_viewers = {
        run_id: viewer
        for run_id, viewer in cache.items()
        if run_id in active_run_ids
    }
