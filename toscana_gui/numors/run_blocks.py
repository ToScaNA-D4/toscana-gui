from __future__ import annotations

from html import escape
from typing import Any

from toscana_gui.ui.run_block_viewer import (
    build_run_block_options,
    clamp_run_block_selection,
    render_run_block_plot_display,
)


def update_numors_block_select(shell: Any, options: dict[str, int], value: int) -> None:
    shell._suspend_numors_events = True
    shell.numors_block_select.options = options
    shell.numors_block_select.value = value
    shell._suspend_numors_events = False


def latest_numors_run_blocks(shell: Any) -> list[dict] | None:
    if shell.current_project_state is None:
        return None
    latest_record = next(
        (record for record in reversed(shell.current_project_state.runs) if record.workflow == "numors"),
        None,
    )
    if latest_record is None:
        return None
    payload = getattr(latest_record, "workflow_data", None)
    if not isinstance(payload, dict):
        return None
    blocks = payload.get("run_blocks")
    if not isinstance(blocks, list):
        return None
    return blocks


def latest_selected_numors_plot_files(shell: Any) -> list[str]:
    blocks = latest_numors_run_blocks(shell) or []
    if not blocks:
        return []
    state = shell._get_numors_state()
    block_index = state.get("selected_run_block_index", 0)
    if not isinstance(block_index, int):
        block_index = 0
    block_index = max(0, min(block_index, len(blocks) - 1))
    block = blocks[block_index] if isinstance(blocks[block_index], dict) else {}
    plot_files = block.get("plot_files", [])
    return list(plot_files) if isinstance(plot_files, list) else []


def resolve_numors_block_selection(
    run_blocks: list[dict],
    numors_state: dict,
) -> tuple[int, int, list[str]]:
    block_index_raw = numors_state.get("selected_run_block_index", 0)
    block_index = int(block_index_raw) if isinstance(block_index_raw, int) else 0
    plot_index_raw = numors_state.get("selected_run_block_plot_index", 0)
    plot_index = int(plot_index_raw) if isinstance(plot_index_raw, int) else 0
    block_index, plot_index, _block, plot_files = clamp_run_block_selection(
        run_blocks,
        block_index,
        plot_index,
    )
    return block_index, plot_index, plot_files


def refresh_numors_run_blocks_view(shell: Any, latest_record: Any = None) -> None:
    if latest_record is None and shell.current_project_state is not None:
        latest_record = next(
            (record for record in reversed(shell.current_project_state.runs) if record.workflow == "numors"),
            None,
        )

    workflow_data = getattr(latest_record, "workflow_data", None) if latest_record is not None else None
    run_blocks = workflow_data.get("run_blocks") if isinstance(workflow_data, dict) else None

    if not isinstance(run_blocks, list) or not run_blocks:
        shell.numors_run_blocks_card.visible = False
        return

    run_id = str(getattr(latest_record, "run_id", "") or "").strip() if latest_record is not None else ""

    state = shell._get_numors_state()
    block_index, plot_index, plot_files = resolve_numors_block_selection(run_blocks, state)

    if (
        state.get("selected_run_block_index") != block_index
        or state.get("selected_run_block_plot_index") != plot_index
    ):
        state["selected_run_block_index"] = block_index
        state["selected_run_block_plot_index"] = plot_index
        shell._persist_numors_state(state)

    options = build_run_block_options(run_blocks)
    if options:
        update_numors_block_select(shell, options, block_index)

    # Match Normalization/Self header dropdown styling: keep the tooltip icon vertically centered
    # by removing the widget label from the row layout.
    if hasattr(shell, "numors_block_select"):
        shell.numors_block_select.name = ""

    shell.numors_prev_block_button.disabled = shell.operation_in_progress or block_index <= 0
    shell.numors_next_block_button.disabled = (
        shell.operation_in_progress or block_index >= len(run_blocks) - 1
    )
    shell.numors_prev_plot_button.disabled = (
        shell.operation_in_progress or plot_index <= 0 or not plot_files
    )
    shell.numors_next_plot_button.disabled = (
        shell.operation_in_progress or not plot_files or plot_index >= len(plot_files) - 1
    )

    block = run_blocks[block_index] if isinstance(run_blocks[block_index], dict) else {}
    label = str(block.get("label") or f"Block {block_index + 1}")
    status = str(block.get("status") or "unknown")
    file_base = block.get("file_base")
    num_range = block.get("num")
    adat_file = block.get("adat_file")
    qdat_file = block.get("qdat_file")

    if hasattr(shell, "numors_block_details"):
        shell.numors_block_details.object = ""
    if hasattr(shell, "numors_block_plot_counter"):
        shell.numors_block_plot_counter.object = ""
    if hasattr(shell, "numors_block_info_hover"):
        shell.numors_block_info_hover.value = _build_block_info_tooltip_html(
            run_id=run_id,
            label=label,
            status=status,
            file_base=file_base,
            num_range=num_range,
            adat_file=adat_file,
            qdat_file=qdat_file,
        )

    render_run_block_plot_display(
        shell.numors_block_plot_display,
        plot_files=plot_files,
        plot_index=plot_index,
        empty_message="Rerun d4creg to capture plots per `<run>` block.",
    )
    if hasattr(shell, "numors_block_view_label"):
        shell.numors_block_view_label.object = (
            f"Currently Viewing Block {block_index + 1}/{len(run_blocks)}"
        )
    if hasattr(shell, "numors_plot_view_label"):
        if plot_files:
            shell.numors_plot_view_label.object = (
                f"Currently Viewing Plot {plot_index + 1}/{len(plot_files)}"
            )
        else:
            shell.numors_plot_view_label.object = "Currently Viewing Plot: No plots"

    shell.numors_run_blocks_card.visible = True


def _fmt_path(value: object) -> str:
    raw = str(value).strip() if value is not None else ""
    if not raw:
        return "<em>missing</em>"
    return (
        "<code style=\"white-space: normal; overflow-wrap: anywhere; "
        "word-break: break-word;\">"
        f"{escape(raw)}"
        "</code>"
    )


def _build_block_info_tooltip_html(
    *,
    run_id: str,
    label: str,
    status: str,
    file_base: object,
    num_range: object,
    adat_file: object,
    qdat_file: object,
) -> str:
    run_id_html = _fmt_path(run_id)
    label_html = escape(label)
    out_html = _fmt_path(file_base)
    num_html = _fmt_path(num_range)
    adat_html = _fmt_path(adat_file)
    qdat_html = _fmt_path(qdat_file)

    return f"""
    <div style="max-width: 320px; line-height: 1.6; white-space: normal; overflow-wrap: anywhere; word-break: break-word;">
      <div><strong>Run ID:</strong> {run_id_html}</div>
      <div><strong>Title:</strong> {label_html}</div>
      <div><strong>Status:</strong> <code style="white-space: normal; overflow-wrap: anywhere; word-break: break-word;">{escape(status)}</code></div>
      <div><strong>out:</strong> {out_html}</div>
      <div><strong>num:</strong> {num_html}</div>
      <div><strong>adat:</strong> {adat_html}</div>
      <div><strong>qdat:</strong> {qdat_html}</div>
    </div>
    """.strip()


def _build_block_info_hovercard_html(
    *,
    status: str,
    file_base: object,
    num_range: object,
    adat_file: object,
    qdat_file: object,
) -> str:
    """Compatibility shim for older tests/helpers (now rendered via TooltipIcon)."""
    return _build_block_info_tooltip_html(
        run_id="",
        label="",
        status=status,
        file_base=file_base,
        num_range=num_range,
        adat_file=adat_file,
        qdat_file=qdat_file,
    )


def on_numors_block_select_change(shell: Any, event: Any) -> None:
    if shell._suspend_numors_events or shell.current_project_state is None:
        return
    if event.new is None:
        return
    try:
        index = int(event.new)
    except (TypeError, ValueError):
        return
    blocks = latest_numors_run_blocks(shell) or []
    if not blocks:
        return
    index = max(0, min(index, len(blocks) - 1))
    state = shell._get_numors_state()
    state["selected_run_block_index"] = index
    state["selected_run_block_plot_index"] = 0
    shell._persist_numors_state(state)
    refresh_numors_run_blocks_view(shell)


def on_numors_prev_run_block(shell: Any, _event: Any = None) -> None:
    if shell.operation_in_progress or shell.current_project_state is None:
        return
    blocks = latest_numors_run_blocks(shell) or []
    if not blocks:
        return
    state = shell._get_numors_state()
    current = int(state.get("selected_run_block_index", 0))
    state["selected_run_block_index"] = max(0, current - 1)
    state["selected_run_block_plot_index"] = 0
    shell._persist_numors_state(state)
    refresh_numors_run_blocks_view(shell)


def on_numors_next_run_block(shell: Any, _event: Any = None) -> None:
    if shell.operation_in_progress or shell.current_project_state is None:
        return
    blocks = latest_numors_run_blocks(shell) or []
    if not blocks:
        return
    state = shell._get_numors_state()
    current = int(state.get("selected_run_block_index", 0))
    state["selected_run_block_index"] = min(len(blocks) - 1, current + 1)
    state["selected_run_block_plot_index"] = 0
    shell._persist_numors_state(state)
    refresh_numors_run_blocks_view(shell)


def on_numors_prev_plot(shell: Any, _event: Any = None) -> None:
    if shell.operation_in_progress or shell.current_project_state is None:
        return
    plots = latest_selected_numors_plot_files(shell)
    if not plots:
        return
    state = shell._get_numors_state()
    current = int(state.get("selected_run_block_plot_index", 0))
    state["selected_run_block_plot_index"] = max(0, current - 1)
    shell._persist_numors_state(state)
    refresh_numors_run_blocks_view(shell)


def on_numors_next_plot(shell: Any, _event: Any = None) -> None:
    if shell.operation_in_progress or shell.current_project_state is None:
        return
    plots = latest_selected_numors_plot_files(shell)
    if not plots:
        return
    state = shell._get_numors_state()
    current = int(state.get("selected_run_block_plot_index", 0))
    state["selected_run_block_plot_index"] = min(len(plots) - 1, current + 1)
    shell._persist_numors_state(state)
    refresh_numors_run_blocks_view(shell)
