from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import plotly.graph_objects as go


@dataclass(frozen=True, slots=True)
class SeriesSpec:
    label: str
    data: Any


def _has_error_column(arr: np.ndarray) -> bool:
    return isinstance(arr, np.ndarray) and arr.ndim == 2 and arr.shape[1] >= 3


def _xy_from_series(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if not isinstance(arr, np.ndarray) or arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError("Expected a 2D numpy array with at least 2 columns.")
    return arr[:, 0], arr[:, 1]


def _error_y_from_series(arr: np.ndarray) -> np.ndarray | None:
    if _has_error_column(arr):
        return arr[:, 2]
    return None


def build_raw_data_figure(
    measurement,
    *,
    show_error_bars: bool,
    title: str | None = None,
) -> go.Figure:
    fig = go.Figure()

    specs = [
        SeriesSpec("Sample", getattr(measurement, "Data", None)),
        SeriesSpec("Container", getattr(measurement, "conData", None)),
        SeriesSpec("Vanadium", getattr(measurement, "norData", None)),
        SeriesSpec("Environment", getattr(measurement, "envData", None)),
        SeriesSpec("Absorber", getattr(measurement, "absData", None)),
    ]

    for spec in specs:
        if spec.data is None:
            continue
        x, y = _xy_from_series(spec.data)
        trace_kwargs = {}
        if show_error_bars:
            err = _error_y_from_series(spec.data)
            if err is not None:
                trace_kwargs["error_y"] = {"type": "data", "array": err, "visible": True}
        fig.add_trace(go.Scatter(x=x, y=y, name=spec.label, mode="lines", **trace_kwargs))

    effective_title = title or getattr(measurement, "Title", None) or "Raw data"
    fig.update_layout(
        title=str(effective_title),
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        # legend_title_text="Data",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        transition={"duration": 0},
        width=1000,
        height=600,
        autosize=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1,           
            xanchor="left",
            x=0.25,            # Slid slightly inward from the left axis
            bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent backdrop
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_direct_subtraction_figure(
    measurement,
    *,
    show_error_bars: bool,
) -> go.Figure:
    sample = getattr(measurement, "Data", None)
    container = getattr(measurement, "conData", None)
    if sample is None or container is None:
        raise ValueError("Sample and Container data are required.")

    x_sample, y_sample = _xy_from_series(sample)
    x_container, y_container = _xy_from_series(container)
    if not np.array_equal(x_sample, x_container):
        raise ValueError("Sample and container x-grids do not match.")

    y_sub = y_sample - y_container

    trace_kwargs = {}
    if show_error_bars:
        s_err = _error_y_from_series(sample)
        c_err = _error_y_from_series(container)
        if s_err is not None and c_err is not None:
            sub_err = np.sqrt(np.square(s_err) + np.square(c_err))
            trace_kwargs["error_y"] = {"type": "data", "array": sub_err, "visible": True}

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_sample,
            y=y_sub,
            name="Direct Sample Subtraction (Sample - Container)",
            mode="lines",
            **trace_kwargs,
        )
    )
    fig.update_layout(
        title="Direct Sample Subtraction (Sample - Container)",
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        transition={"duration": 0},
        width=800,
        height=600,
        autosize=False,
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_linear_combination_chi_figure(
    trans: list[float],
    chi: list[float],
    fitted: list[float],
    *,
    best_t: float | None,
    effective_t: float | None,
    t_mode: str | None = None,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trans,
            y=chi,
            name="χ (RMS diff)",
            mode="markers+lines",
        )
    )
    if fitted and len(fitted) == len(trans):
        fig.add_trace(
            go.Scatter(
                x=trans,
                y=fitted,
                name="2nd-degree fit",
                mode="lines",
            )
    )
    selected_mode = str(t_mode or "computed").strip().lower()
    if selected_mode == "custom":
        if effective_t is not None:
            fig.add_vline(
                x=float(effective_t),
                line_dash="dash",
                line_color="black",
                annotation_text=f"Custom t = {effective_t:.2f}",
                annotation_position="top left",
            )
    else:
        if best_t is not None:
            fig.add_vline(
                x=float(best_t),
                line_dash="dash",
                line_color="gray",
                annotation_text=f"Computed t = {best_t:.2f}",
                annotation_position="top left",
            )

    fig.update_layout(
        title="Linear Combination: χ vs t",
        xaxis_title="t (sample)",
        yaxis_title="χ",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        transition={"duration": 0},
        width=800,
        height=600,
        autosize=False,
        legend=dict(
            yanchor="bottom",
            y=0.05,          
            xanchor="left",
            x=0.05,         
            bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent white background
            bordercolor="rgba(0, 0, 0, 0.2)",    # Subtle border
            borderwidth=1
        )
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_linear_combination_subtraction_figure(
    *,
    x: np.ndarray,
    sample_y: np.ndarray,
    background_y: np.ndarray,
    subtracted_y: np.ndarray,
    direct_subtracted_y: np.ndarray | None,
    title: str,
    error_y: np.ndarray | None = None,
) -> go.Figure:
    fig = go.Figure()
    trace_kwargs = {}
    if error_y is not None:
        trace_kwargs["error_y"] = {"type": "data", "array": error_y, "visible": True}

    fig.add_trace(
        go.Scatter(
            x=x,
            y=subtracted_y,
            name="Sample - (t*Container + (1-t)*Environment)",
            mode="lines",
            **trace_kwargs,
        )
    )
    if direct_subtracted_y is not None:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=direct_subtracted_y,
                name="Sample - Container (direct)",
                mode="lines",
            )
        )
    fig.add_trace(go.Scatter(x=x, y=sample_y, name="Sample", mode="lines"))
    fig.add_trace(go.Scatter(x=x, y=background_y, name="Background", mode="lines"))

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        transition={"duration": 0},
        width=800,
        height=600,
        autosize=False,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,           
            xanchor="left",
            x=0,            
            bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent backdrop
        ),

    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_vanadium_chi_figure(
    trans: list[float],
    chi: list[float],
    fitted: list[float],
    *,
    best_t: float | None,
    effective_t: float | None,
    t_mode: str | None = None,
) -> go.Figure:
    fig = build_linear_combination_chi_figure(
        trans,
        chi,
        fitted,
        best_t=best_t,
        effective_t=effective_t,
        t_mode=t_mode,
    )
    fig.update_layout(
        title="Vanadium: χ vs t",
        xaxis_title="t (vanadium)",
    )
    return fig


def build_vanadium_subtraction_figure(
    *,
    x: np.ndarray,
    vanadium_y: np.ndarray,
    background_y: np.ndarray,
    subtracted_y: np.ndarray,
    title: str,
    error_y: np.ndarray | None = None,
) -> go.Figure:
    fig = go.Figure()
    trace_kwargs = {}
    if error_y is not None:
        trace_kwargs["error_y"] = {"type": "data", "array": error_y, "visible": True}

    fig.add_trace(
        go.Scatter(
            x=x,
            y=subtracted_y,
            name="Vanadium - Background",
            mode="lines",
            **trace_kwargs,
        )
    )
    fig.add_trace(go.Scatter(x=x, y=vanadium_y, name="Vanadium (in environment)", mode="lines"))
    fig.add_trace(go.Scatter(x=x, y=background_y, name="Background (t*Environment)", mode="lines"))

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        transition={"duration": 0},
        width=800,
        height=600,
        autosize=False,
        legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1,           
        xanchor="left",
        x=0,            
        bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent backdrop
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_final_background_subtracted_signals_figure(
    *,
    x: np.ndarray,
    sample_subtracted_y: np.ndarray,
    vanadium_subtracted_y: np.ndarray,
    title: str,
    sample_error_y: np.ndarray | None = None,
    vanadium_error_y: np.ndarray | None = None,
) -> go.Figure:
    fig = go.Figure()

    sample_kwargs = {}
    if sample_error_y is not None:
        sample_kwargs["error_y"] = {"type": "data", "array": sample_error_y, "visible": True}

    vanadium_kwargs = {}
    if vanadium_error_y is not None:
        vanadium_kwargs["error_y"] = {"type": "data", "array": vanadium_error_y, "visible": True}

    fig.add_trace(
        go.Scatter(
            x=x,
            y=sample_subtracted_y,
            name="Sample (linear-combination subtracted)",
            mode="lines",
            **sample_kwargs,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=vanadium_subtracted_y,
            name="Vanadium (environment subtracted)",
            mode="lines",
            **vanadium_kwargs,
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1,           
        xanchor="left",
        x=0.25,            # Slid slightly inward from the left axis
        bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent backdrop
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig
