from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import panel as pn


@dataclass(slots=True)
class RunBlockPlotDisplay:
    container: pn.Column
    message_pane: pn.pane.Markdown
    image_pane: pn.pane.PNG


def clamp_run_block_selection(
    run_blocks: list[dict],
    block_index: int,
    plot_index: int,
) -> tuple[int, int, dict, list[str]]:
    if not run_blocks:
        return 0, 0, {}, []

    block_index = _clamp_index(block_index, len(run_blocks))
    block = run_blocks[block_index] if isinstance(run_blocks[block_index], dict) else {}
    plot_files = block.get("plot_files", [])
    plot_files = list(plot_files) if isinstance(plot_files, list) else []
    plot_index = _clamp_index(plot_index, len(plot_files))
    return block_index, plot_index, block, plot_files


def build_run_block_options(run_blocks: list[dict]) -> dict[str, int]:
    options: dict[str, int] = {}
    for idx, block in enumerate(run_blocks):
        if not isinstance(block, dict):
            continue
        label = str(block.get("label") or f"Block {idx + 1}")
        options[f"{idx + 1}: {label}"] = idx
    return options


def build_run_block_details_markdown(
    *,
    run_blocks: list[dict],
    block_index: int,
    block: dict,
    plot_files: list[str],
) -> str:
    label = str(block.get("label") or f"Block {block_index + 1}")
    status = str(block.get("status") or "unknown")
    file_base = block.get("file_base")
    num_range = block.get("num")
    adat_file = block.get("adat_file")
    qdat_file = block.get("qdat_file")

    details_lines = [
        f"**Block:** `{block_index + 1}` / `{len(run_blocks)}`",
        f"**Title:** {label}",
        f"**Status:** `{status}`",
    ]
    if file_base:
        details_lines.append(f"**out:** `{file_base}`")
    if num_range:
        details_lines.append(f"**num:** `{num_range}`")
    details_lines.append(f"**adat:** `{adat_file}`" if adat_file else "**adat:** missing")
    details_lines.append(f"**qdat:** `{qdat_file}`" if qdat_file else "**qdat:** missing")
    details_lines.append(f"**plots:** `{len(plot_files)}`")
    return "\n".join(details_lines)


def summarize_run_blocks(run_blocks: list[dict]) -> tuple[int, int, list[str]]:
    succeeded_blocks = 0
    failed_blocks = 0
    block_lines: list[str] = []

    for idx, block in enumerate(run_blocks, start=1):
        if not isinstance(block, dict):
            continue
        status = str(block.get("status") or "unknown")
        if status == "succeeded":
            succeeded_blocks += 1
        elif status == "failed":
            failed_blocks += 1

        label = str(block.get("label") or f"Block {idx}")
        file_base = block.get("file_base")
        num_range = block.get("num")
        adat_file = block.get("adat_file")
        qdat_file = block.get("qdat_file")
        plot_files = block.get("plot_files", [])
        plot_count = len(plot_files) if isinstance(plot_files, list) else 0

        parts = [f"[{idx}] `{status}` - {label}"]
        if file_base:
            parts.append(f"out=`{file_base}`")
        if num_range:
            parts.append(f"num=`{num_range}`")
        parts.append("adat=missing" if not adat_file else f"adat=`{adat_file}`")
        parts.append("qdat=missing" if not qdat_file else f"qdat=`{qdat_file}`")
        parts.append(f"plots=`{plot_count}`")
        block_lines.append("- " + ", ".join(parts))

    return succeeded_blocks, failed_blocks, block_lines


def create_run_block_plot_display(
    *,
    width: int = 720,
    height: int = 480,
) -> RunBlockPlotDisplay:
    message_pane = pn.pane.Markdown("", sizing_mode="stretch_width", visible=False)
    image_pane = pn.pane.PNG(
        None,
        width=width,
        height=height,
        sizing_mode="fixed",
        visible=False,
    )
    container = pn.Column(
        message_pane,
        image_pane,
        sizing_mode="stretch_width",
    )
    return RunBlockPlotDisplay(
        container=container,
        message_pane=message_pane,
        image_pane=image_pane,
    )


def render_run_block_plot_display(
    display: RunBlockPlotDisplay,
    *,
    plot_files: list[str],
    plot_index: int,
    empty_message: str,
) -> str:
    if plot_files:
        current_plot = plot_files[plot_index]
        if Path(str(current_plot)).exists():
            display.message_pane.object = ""
            display.message_pane.visible = False
            display.image_pane.object = current_plot
            display.image_pane.visible = True
        else:
            display.image_pane.object = None
            display.image_pane.visible = False
            display.message_pane.object = f"Plot file not found: `{current_plot}`"
            display.message_pane.visible = True
        return f"Plot `{plot_index + 1}` / `{len(plot_files)}`"

    display.image_pane.object = None
    display.image_pane.visible = False
    display.message_pane.object = empty_message
    display.message_pane.visible = True
    return "No per-block plots recorded for this run."


def _clamp_index(index: int, size: int) -> int:
    if size <= 0:
        return 0
    return max(0, min(index, size - 1))
