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


def update_self_lowq_figure(
    fig: go.Figure,
    *,
    q: np.ndarray,
    dsdo: np.ndarray,
    q_subset: np.ndarray | None = None,
    dsdo_subset: np.ndarray | None = None,
    corrected: np.ndarray | None = None,
    show_corrected: bool = False,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-lowq",
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    dsdo = np.asarray(dsdo, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]
    dsdo_sorted = dsdo[order]

    fig.data = []

    if show_corrected and corrected is not None:
        corrected = np.asarray(corrected, dtype=float)
        corrected_sorted = corrected[order] if corrected.shape == q.shape else corrected
        fig.add_trace(
            go.Scatter(
                x=q_sorted,
                y=corrected_sorted,
                name="Corrected",
                mode="lines",
                line={"color": "rgba(37, 99, 235, 0.92)", "width": 2.4},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=q_sorted,
                y=dsdo_sorted,
                name="Raw",
                mode="lines",
                line={"color": "rgba(0, 0, 0, 0.80)", "width": 1.6, "dash": "dot"},
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=q_sorted,
                y=dsdo_sorted,
                name="Raw",
                mode="lines",
                line={"color": "rgba(37, 99, 235, 0.88)", "width": 2.2},
            )
        )

    has_subset = q_subset is not None and dsdo_subset is not None and len(q_subset)
    if has_subset and not show_corrected:
        q_subset = np.asarray(q_subset, dtype=float)
        dsdo_subset = np.asarray(dsdo_subset, dtype=float)
        order_subset = np.argsort(q_subset)
        q_subset = q_subset[order_subset]
        dsdo_subset = dsdo_subset[order_subset]
        fig.add_trace(
            go.Scatter(
                x=q_subset,
                y=dsdo_subset,
                name="Fit points",
                mode="lines",
                marker={"color": "rgba(220, 38, 38, 0.92)", "size": 8, "line": {"width": 0}},
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
        legend=dict(
            x=1,
            y=0,
            xanchor="right",
            yanchor="top",
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_self_lowq_figure(
    *,
    q: np.ndarray,
    dsdo: np.ndarray,
    q_subset: np.ndarray | None = None,
    dsdo_subset: np.ndarray | None = None,
    corrected: np.ndarray | None = None,
    show_corrected: bool = False,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-lowq",
) -> go.Figure:
    fig = go.Figure()
    update_self_lowq_figure(
        fig,
        q=q,
        dsdo=dsdo,
        q_subset=q_subset,
        dsdo_subset=dsdo_subset,
        corrected=corrected,
        show_corrected=show_corrected,
        title=title,
        width=width,
        height=height,
        uirevision=uirevision,
    )

    # Stable "Home" view at creation time.
    q_bounds = _finite_min_max(np.asarray(q, dtype=float))
    y_series = np.asarray(corrected if (show_corrected and corrected is not None) else dsdo, dtype=float)
    y_bounds = _finite_min_max(y_series)
    if q_bounds is not None:
        x0, x1 = _pad_range(q_bounds[0], q_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)

    return fig


def update_self_fit_model_figure(
    fig: go.Figure,
    *,
    q: np.ndarray,
    y: np.ndarray,
    y_fit: np.ndarray,
    q_subset: np.ndarray | None = None,
    y_subset: np.ndarray | None = None,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-fit-model",
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    y = np.asarray(y, dtype=float)
    y_fit = np.asarray(y_fit, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]
    y_sorted = y[order]
    y_fit_sorted = y_fit[order] if y_fit.shape == q.shape else y_fit

    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=q_sorted,
            y=y_sorted,
            name="Corrected",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.90)", "width": 2.2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=q_sorted,
            y=y_fit_sorted,
            name="Fit",
            mode="lines",
            line={"color": "rgba(220, 38, 38, 0.88)", "width": 2.2},
        )
    )

    if q_subset is not None and y_subset is not None and len(q_subset):
        q_subset = np.asarray(q_subset, dtype=float)
        y_subset = np.asarray(y_subset, dtype=float)
        order_subset = np.argsort(q_subset)
        q_subset = q_subset[order_subset]
        y_subset = y_subset[order_subset]
        fig.add_trace(
            go.Scatter(
                x=q_subset,
                y=y_subset,
                name="Fit points",
                mode="lines",
                #marker={"color": "rgba(15, 23, 42, 0.88)", "size": 6, "line": {"width": 0}},
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
        legend=dict(
            x=1,
            y=0,
            xanchor="right",
            yanchor="top",
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_self_fit_model_figure(
    *,
    q: np.ndarray,
    y: np.ndarray,
    y_fit: np.ndarray,
    q_subset: np.ndarray | None = None,
    y_subset: np.ndarray | None = None,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-fit-model",
) -> go.Figure:
    fig = go.Figure()
    update_self_fit_model_figure(
        fig,
        q=q,
        y=y,
        y_fit=y_fit,
        q_subset=q_subset,
        y_subset=y_subset,
        title=title,
        width=width,
        height=height,
        uirevision=uirevision,
    )

    q_bounds = _finite_min_max(np.asarray(q, dtype=float))
    y_bounds = _finite_min_max(np.asarray(y, dtype=float))
    if q_bounds is not None:
        x0, x1 = _pad_range(q_bounds[0], q_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    return fig


def update_static_structure_factor_figure(
    fig: go.Figure,
    *,
    q: np.ndarray,
    soq: np.ndarray,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-soq",
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    soq = np.asarray(soq, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]
    soq_sorted = soq[order]

    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=q_sorted,
            y=soq_sorted,
            name="S(Q)",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.88)", "width": 2.2},
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Q (Å⁻¹)",        
        yaxis_title="S(Q)",
        margin=dict(l=40, r=20, t=60, b=40),
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
            yanchor="top",
        ),
    )
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")

    q_bounds = _finite_min_max(np.asarray(q_sorted, dtype=float))
    y_bounds = _finite_min_max(np.asarray(soq_sorted, dtype=float))
    if q_bounds is not None:
        x0, x1 = _pad_range(q_bounds[0], q_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    return fig


def build_static_structure_factor_figure(
    *,
    q: np.ndarray,
    soq: np.ndarray,
    title: str | None = None,
    width: int = 800,
    height: int = 600,
    uirevision: str = "self-soq",
) -> go.Figure:
    fig = go.Figure()
    update_static_structure_factor_figure(
        fig,
        q=q,
        soq=soq,
        title=title,
        width=width,
        height=height,
        uirevision=uirevision,
    )
    return fig

