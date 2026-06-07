from __future__ import annotations

import numpy as np
import plotly.graph_objects as go


def _finite_min_max(values: np.ndarray) -> tuple[float, float] | None:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return None
    v_min = float(np.nanmin(finite))
    v_max = float(np.nanmax(finite))
    if not np.isfinite(v_min) or not np.isfinite(v_max):
        return None
    if v_max < v_min:
        v_min, v_max = v_max, v_min
    return v_min, v_max


def _pad_range(v_min: float, v_max: float, *, frac: float, min_pad: float) -> tuple[float, float]:
    span = float(v_max - v_min)
    if not np.isfinite(span) or span <= 0:
        pad = max(abs(float(v_min)) * frac, 1.0)
        return float(v_min - pad), float(v_max + pad)
    pad = max(span * frac, min_pad)
    return float(v_min - pad), float(v_max + pad)


def update_vanadium_fit_selection_figure(
    fig: go.Figure,
    *,
    q_all: np.ndarray,
    y_all: np.ndarray,
    q_subset: np.ndarray | None = None,
    y_subset: np.ndarray | None = None,
    q_focus_min: float | None = None,
    q_focus_max: float | None = None,
    y_axis_min: float | None = None,
    y_axis_max: float | None = None,
    title: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> go.Figure:
    q_all = np.asarray(q_all, dtype=float)
    y_all = np.asarray(y_all, dtype=float)
    order_all = np.argsort(q_all)
    q_all_sorted = q_all[order_all]
    y_all_sorted = y_all[order_all]

    def _finite_in_q_window(
        q_values: np.ndarray,
        y_values: np.ndarray,
        *,
        q_min: float | None,
        q_max: float | None,
    ) -> np.ndarray:
        mask = np.isfinite(q_values) & np.isfinite(y_values)
        if q_min is not None and np.isfinite(q_min):
            mask &= q_values >= float(q_min)
        if q_max is not None and np.isfinite(q_max):
            mask &= q_values <= float(q_max)
        return mask

    if len(fig.data) == 0:
        fig.add_trace(go.Scatter())
    fig.data[0].update(
        x=q_all_sorted,
        y=y_all_sorted,
        name="Data",
        mode="lines",
        line={"color": "rgba(37, 99, 235, 0.88)", "width": 2},
    )

    has_subset = q_subset is not None and y_subset is not None and len(q_subset)
    if has_subset:
        q_subset = np.asarray(q_subset, dtype=float)
        y_subset = np.asarray(y_subset, dtype=float)
        order_subset = np.argsort(q_subset)
        q_subset_sorted = q_subset[order_subset]
        y_subset_sorted = y_subset[order_subset]
        if len(fig.data) < 2:
            fig.add_trace(go.Scatter())
        fig.data[1].update(
            x=q_subset_sorted,
            y=y_subset_sorted,
            name="Data used in fit",
            mode="lines",
            line={"color": "rgba(220, 38, 38, 0.92)", "width": 2.5},
        )
        if len(fig.data) > 2:
            fig.data = fig.data[:2]
    else:
        if len(fig.data) > 1:
            fig.data = fig.data[:1]

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="Intensity (arbitrary units)",
        legend_title_text="Series",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision="vanadium-fit-selection",
        transition={"duration": 0},
        width=int(width if width is not None else (int(getattr(fig.layout, "width", 0) or 0) or 860)),
        height=int(height if height is not None else (int(getattr(fig.layout, "height", 0) or 0) or 660)),
        autosize=False,
        legend=dict(
        x=1,
        y=0,
        xanchor="right",
        yanchor="bottom",
    ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_vanadium_fit_selection_figure(
    *,
    q_all: np.ndarray,
    y_all: np.ndarray,
    q_subset: np.ndarray | None = None,
    y_subset: np.ndarray | None = None,
    q_focus_min: float | None = None,
    q_focus_max: float | None = None,
    y_axis_min: float | None = None,
    y_axis_max: float | None = None,
    title: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> go.Figure:
    fig = go.Figure()
    update_vanadium_fit_selection_figure(
        fig,
        q_all=q_all,
        y_all=y_all,
        q_subset=q_subset,
        y_subset=y_subset,
        q_focus_min=q_focus_min,
        q_focus_max=q_focus_max,
        y_axis_min=y_axis_min,
        y_axis_max=y_axis_max,
        title=title,
        width=width,
        height=height,
    )

    # Lock in a stable "Home" view based on the full dataset at creation time.
    # Subsequent slider/parameter updates must not change the current viewport;
    # only Plotly's Home button should restore this baseline view.
    q_bounds = _finite_min_max(np.asarray(q_all, dtype=float))
    y_bounds = _finite_min_max(np.asarray(y_all, dtype=float))
    if q_bounds is not None:
        x0, x1 = _pad_range(q_bounds[0], q_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)

    return fig


def update_sample_normalization_figure(
    fig: go.Figure,
    *,
    q: np.ndarray,
    dsdo: np.ndarray,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    y_min: float | None = 0.0,
    y_max: float | None = 6.0,
    uirevision: str = "sample-normalization",
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    dsdo = np.asarray(dsdo, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]
    dsdo_sorted = dsdo[order]

    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=q_sorted,
            y=dsdo_sorted,
            name="Sample",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.88)", "width": 2},
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="(1/N) dσ/dΩ (barns/sr/atom)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=uirevision,
        transition={"duration": 0},
        width=int(width),
        height=int(height),
        autosize=False,
        showlegend=False,
    )
    if y_min is not None and y_max is not None and np.isfinite(float(y_min)) and np.isfinite(float(y_max)):
        fig.update_yaxes(range=[float(y_min), float(y_max)], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_sample_normalization_figure(
    *,
    q: np.ndarray,
    dsdo: np.ndarray,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    y_min: float | None = 0.0,
    y_max: float | None = 6.0,
    uirevision: str = "sample-normalization",
) -> go.Figure:
    fig = go.Figure()
    update_sample_normalization_figure(
        fig,
        q=q,
        dsdo=dsdo,
        title=title,
        width=width,
        height=height,
        y_min=y_min,
        y_max=y_max,
        uirevision=uirevision,
    )
    return fig


def update_vanadium_self_fit_preview_figure(
    fig: go.Figure,
    *,
    q: np.ndarray,
    y: np.ndarray | None,
    norSelf: np.ndarray,
    norsigm: np.ndarray | None,
    norpoly: np.ndarray | None,
    norsigm0: float | None,
    mode: str,
    uirevision: str,
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]

    def _sorted(values: np.ndarray | None) -> np.ndarray | None:
        if values is None:
            return None
        arr = np.asarray(values, dtype=float)
        if arr.shape[0] != q.shape[0]:
            return arr
        return arr[order]

    y_sorted = _sorted(y)
    norSelf_sorted = _sorted(norSelf)
    norsigm_sorted = _sorted(norsigm)
    norpoly_sorted = _sorted(norpoly)

    fig.data = []

    if mode == "Differential cross section":
        from math import pi

        from ntsa.isotopes.core import elemento

        factor = float(elemento("V").sig_sca) / (4.0 * float(pi))
        if (
            y_sorted is not None
            and norpoly_sorted is not None
            and norsigm0 is not None
            and np.isfinite(float(norsigm0))
            and float(norsigm0) != 0
        ):
            with np.errstate(divide="ignore", invalid="ignore"):
                data_cs = factor * (np.asarray(y_sorted, dtype=float) / float(norsigm0)) / np.asarray(norpoly_sorted, dtype=float)
            fig.add_trace(go.Scatter(x=q_sorted, y=data_cs, name="Data (scaled)", mode="lines"))
        if (
            norsigm_sorted is not None
            and norsigm0 is not None
            and np.isfinite(float(norsigm0))
            and float(norsigm0) != 0
        ):
            sig_cs = factor * (np.asarray(norsigm_sorted, dtype=float) / float(norsigm0))
            fig.add_trace(go.Scatter(x=q_sorted, y=sig_cs, name="s(Q)/s(0)", mode="lines"))
        title = "Differential cross section preview"
        y_label = "dσ/dΩ (barns/sr/atom)"
    else:
        if y_sorted is not None:
            fig.add_trace(go.Scatter(x=q_sorted, y=y_sorted, name="Data", mode="lines"))
        if norSelf_sorted is not None:
            fig.add_trace(go.Scatter(x=q_sorted, y=norSelf_sorted, name="Fit", mode="lines"))
        title = "Vanadium self fit preview"
        y_label = "Intensity (arbitrary units)"

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title=y_label,
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode="x unified",
        uirevision=uirevision,
        transition={"duration": 0},
        width=int(width),
        height=int(height),
        autosize=False,
        legend=dict(
            x=1,
            y=0,
            xanchor="right",
            yanchor="bottom",
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_vanadium_self_fit_preview_figure(
    *,
    q: np.ndarray,
    y: np.ndarray | None,
    norSelf: np.ndarray,
    norsigm: np.ndarray | None,
    norpoly: np.ndarray | None,
    norsigm0: float | None,
    mode: str,
    uirevision: str,
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    fig = go.Figure()
    update_vanadium_self_fit_preview_figure(
        fig,
        q=q,
        y=y,
        norSelf=norSelf,
        norsigm=norsigm,
        norpoly=norpoly,
        norsigm0=norsigm0,
        mode=mode,
        uirevision=uirevision,
        width=width,
        height=height,
    )

    q_bounds = _finite_min_max(np.asarray(q, dtype=float))
    if q_bounds is not None:
        x0, x1 = _pad_range(q_bounds[0], q_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)

    return fig
