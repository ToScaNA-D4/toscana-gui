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


def build_ft_real_space_function_figure(
    x: np.ndarray,
    y: np.ndarray,
    *,
    series_label: str,
    xaxis_title: str,
    yaxis_title: str,
    line_color: str,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    order = np.argsort(x) if x.size else np.arange(x.size)
    x_sorted = x[order]
    y_sorted = y[order] if y.shape == x.shape else y

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_sorted,
            y=y_sorted,
            name=str(series_label or ""),
            mode="lines",
            line={"color": str(line_color), "width": 2.2},
        )
    )

    fig.update_layout(
        title=None,
        xaxis_title=str(xaxis_title),
        yaxis_title=str(yaxis_title),
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-real-space:{context_id}" if context_id else "ft-real-space",
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

    x_bounds = _finite_min_max(x_sorted)
    y_bounds = _finite_min_max(np.asarray(y_sorted, dtype=float))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_base_gr_figure(
    *,
    r: np.ndarray,
    gr: np.ndarray,
    gr_lorch: np.ndarray,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    gr = np.asarray(gr, dtype=float)
    gr_lorch = np.asarray(gr_lorch, dtype=float)
    order = np.argsort(r)
    r_sorted = r[order]
    gr_sorted = gr[order] if gr.shape == r.shape else gr
    gr_lorch_sorted = gr_lorch[order] if gr_lorch.shape == r.shape else gr_lorch

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_sorted,
            name="G(R)",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.90)", "width": 2.2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_lorch_sorted,
            name="G(R) (Lorch)",
            mode="lines",
            line={"color": "rgba(255, 0, 0, 0.82)", "width": 2.0},
        )
    )

    fig.update_layout(
        title=None,
        xaxis_title="R",
        yaxis_title="G(R)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-gr:{context_id}" if context_id else "ft-gr",
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

    x_bounds = _finite_min_max(r_sorted)
    y_bounds = _finite_min_max(np.concatenate([np.asarray(gr_sorted, dtype=float), np.asarray(gr_lorch_sorted, dtype=float)]))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_soq_figure(
    *,
    q: np.ndarray,
    soq: np.ndarray,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    q = np.asarray(q, dtype=float)
    soq = np.asarray(soq, dtype=float)
    order = np.argsort(q)
    q_sorted = q[order]
    soq_sorted = soq[order] if soq.shape == q.shape else soq

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=q_sorted,
            y=soq_sorted,
            name="S(Q)",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.90)", "width": 2.2},
        )
    )

    fig.update_layout(
        title=None,
        xaxis_title="Q (Å⁻¹)",
        yaxis_title="S(Q)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-soq:{context_id}" if context_id else "ft-soq",
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

    x_bounds = _finite_min_max(q_sorted)
    y_bounds = _finite_min_max(np.asarray(soq_sorted, dtype=float))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_rho_selection_figure(
    *,
    r: np.ndarray,
    gr: np.ndarray,
    gr_lorch: np.ndarray,
    selected_mask_no_lorch: np.ndarray,
    selected_mask_lorch: np.ndarray,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    gr = np.asarray(gr, dtype=float)
    gr_lorch = np.asarray(gr_lorch, dtype=float)
    selected_mask_no_lorch = np.asarray(selected_mask_no_lorch, dtype=bool)
    selected_mask_lorch = np.asarray(selected_mask_lorch, dtype=bool)

    order = np.argsort(r)
    r_sorted = r[order]
    gr_sorted = gr[order] if gr.shape == r.shape else gr
    gr_lorch_sorted = gr_lorch[order] if gr_lorch.shape == r.shape else gr_lorch
    mask_no_sorted = selected_mask_no_lorch[order] if selected_mask_no_lorch.shape == r.shape else selected_mask_no_lorch
    mask_lorch_sorted = selected_mask_lorch[order] if selected_mask_lorch.shape == r.shape else selected_mask_lorch

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_sorted,
            name="G(R)",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.90)", "width": 2.2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_lorch_sorted,
            name="G(R) (Lorch)",
            mode="lines",
            line={"color": "rgba(255, 0, 0, 0.82)", "width": 2.0},
        )
    )

    # Highlight selected points.
    if mask_no_sorted.shape == r_sorted.shape:
        fig.add_trace(
            go.Scatter(
                x=r_sorted[mask_no_sorted],
                y=gr_sorted[mask_no_sorted],
                name="Selected (G(R))",
                mode="markers",
                marker={"color": "rgba(37, 99, 235, 0.98)", "size": 7},
            )
        )
    if mask_lorch_sorted.shape == r_sorted.shape:
        fig.add_trace(
            go.Scatter(
                x=r_sorted[mask_lorch_sorted],
                y=gr_lorch_sorted[mask_lorch_sorted],
                name="Selected (G(R) (Lorch))",
                mode="markers",
                marker={"color": "rgba(255, 0, 0, 0.92)", "size": 7},
            )
        )

    fig.update_layout(
        title=None,
        xaxis_title="R",
        yaxis_title="G(R)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-rho:select:{context_id}" if context_id else "ft-rho:select",
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

    x_bounds = _finite_min_max(r_sorted)
    y_bounds = _finite_min_max(np.concatenate([np.asarray(gr_sorted, dtype=float), np.asarray(gr_lorch_sorted, dtype=float)]))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_rho_fit_figure(
    *,
    r: np.ndarray,
    gr: np.ndarray,
    gr_lorch: np.ndarray,
    rho_no_lorch: float,
    rho_lorch: float,
    context_id: str = "",
    fit_signature: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    gr = np.asarray(gr, dtype=float)
    gr_lorch = np.asarray(gr_lorch, dtype=float)
    order = np.argsort(r)
    r_sorted = r[order]
    gr_sorted = gr[order] if gr.shape == r.shape else gr
    gr_lorch_sorted = gr_lorch[order] if gr_lorch.shape == r.shape else gr_lorch

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_sorted,
            name="G(R)",
            mode="lines",
            line={"color": "rgba(37, 99, 235, 0.90)", "width": 2.2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=gr_lorch_sorted,
            name="G(R) (Lorch)",
            mode="lines",
            line={"color": "rgba(255, 0, 0, 0.82)", "width": 2.0},
        )
    )

    with np.errstate(all="ignore"):
        fit_no = (-4.0 * float(np.pi) * float(rho_no_lorch)) * r_sorted
        fit_lorch = (-4.0 * float(np.pi) * float(rho_lorch)) * r_sorted
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=fit_no,
            name="Fit (G(R))",
            mode="lines",
            line={"color": "rgba(0, 0, 0, 0.90)", "width": 2.0},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=fit_lorch,
            name="Fit (G(R) (Lorch))",
            mode="lines",
            line={"color": "rgba(0, 0, 0, 0.90)", "width": 2.0},
        )
    )

    sig = fit_signature or "fit"
    fig.update_layout(
        title=None,
        xaxis_title="R",
        yaxis_title="G(R)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-rho:fit:{context_id}:{sig}" if context_id else f"ft-rho:fit:{sig}",
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

    x_bounds = _finite_min_max(r_sorted)
    y_bounds = _finite_min_max(np.concatenate([np.asarray(gr_sorted, dtype=float), np.asarray(gr_lorch_sorted, dtype=float)]))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_rho_selection_figure_single(
    *,
    r: np.ndarray,
    y: np.ndarray,
    selected_mask: np.ndarray,
    series: str,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    fig = go.Figure()
    update_ft_rho_selection_figure_single(
        fig,
        r=r,
        y=y,
        selected_mask=selected_mask,
        series=series,
        context_id=context_id,
        width=width,
        height=height,
    )
    return fig


def update_ft_rho_selection_figure_single(
    fig: go.Figure,
    *,
    r: np.ndarray,
    y: np.ndarray,
    selected_mask: np.ndarray,
    series: str,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    y = np.asarray(y, dtype=float)
    selected_mask = np.asarray(selected_mask, dtype=bool)
    series = str(series or "").strip()

    order = np.argsort(r)
    r_sorted = r[order]
    y_sorted = y[order] if y.shape == r.shape else y
    mask_sorted = selected_mask[order] if selected_mask.shape == r.shape else selected_mask

    if series == "lorch":
        base_name = "G(R) (Lorch)"
        base_line = {"color": "rgba(255, 0, 0, 0.82)", "width": 2.0}
    else:
        base_name = "G(R)"
        base_line = {"color": "rgba(37, 99, 235, 0.90)", "width": 2.2}

    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=y_sorted,
            name=base_name,
            mode="lines",
            line=base_line,
        )
    )

    if mask_sorted.shape == r_sorted.shape:
        fig.add_trace(
            go.Scatter(
                x=r_sorted[mask_sorted],
                y=y_sorted[mask_sorted],
                name="Selected",
                mode="lines",
                line={"color": "rgba(0, 0, 0, 0.95)", "width": 2.6},
                connectgaps=False,
            )
        )

    fig.update_layout(
        title=None,
        xaxis_title="R",
        yaxis_title="G(R)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-rho:select:{context_id}:{series}" if context_id else f"ft-rho:select:{series}",
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

    x_bounds = _finite_min_max(r_sorted)
    y_bounds = _finite_min_max(np.asarray(y_sorted, dtype=float))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_ft_rho_fit_figure_single(
    *,
    r: np.ndarray,
    y: np.ndarray,
    rho: float,
    series: str,
    context_id: str = "",
    fit_signature: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    fig = go.Figure()
    update_ft_rho_fit_figure_single(
        fig,
        r=r,
        y=y,
        rho=rho,
        series=series,
        context_id=context_id,
        fit_signature=fit_signature,
        width=width,
        height=height,
    )
    return fig


def update_ft_rho_fit_figure_single(
    fig: go.Figure,
    *,
    r: np.ndarray,
    y: np.ndarray,
    rho: float,
    series: str,
    context_id: str = "",
    fit_signature: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    y = np.asarray(y, dtype=float)
    series = str(series or "").strip()
    order = np.argsort(r)
    r_sorted = r[order]
    y_sorted = y[order] if y.shape == r.shape else y

    if series == "lorch":
        base_name = "G(R) (Lorch)"
        base_line = {"color": "rgba(255, 0, 0, 0.82)", "width": 2.0}
        fit_name = "Fit (G(R) (Lorch))"
        fit_line = {"color": "rgba(0, 0, 0, 0.90)", "width": 2.0, "dash": "dot"}
    else:
        base_name = "G(R)"
        base_line = {"color": "rgba(37, 99, 235, 0.90)", "width": 2.2}
        fit_name = "Fit (G(R))"
        fit_line = {"color": "rgba(0, 0, 0, 0.90)", "width": 2.0, "dash": "dot"}


    fig.data = []
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=y_sorted,
            name=base_name,
            mode="lines",
            line=base_line,
        )
    )

    with np.errstate(all="ignore"):
        fit_y = (-4.0 * float(np.pi) * float(rho)) * r_sorted
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=fit_y,
            name=fit_name,
            mode="lines",
            line=fit_line
        )
    )

    sig = fit_signature or "fit"
    fig.update_layout(
        title=None,
        xaxis_title="R",
        yaxis_title="G(R)",
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        uirevision=f"ft-rho:fit:{context_id}:{series}:{sig}" if context_id else f"ft-rho:fit:{series}:{sig}",
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

    x_bounds = _finite_min_max(r_sorted)
    y_bounds = _finite_min_max(np.asarray(y_sorted, dtype=float))
    if x_bounds is not None:
        x0, x1 = _pad_range(x_bounds[0], x_bounds[1], frac=0.02, min_pad=1e-6)
        fig.update_xaxes(range=[x0, x1], autorange=False)
    if y_bounds is not None:
        y0, y1 = _pad_range(y_bounds[0], y_bounds[1], frac=0.03, min_pad=1e-6)
        fig.update_yaxes(range=[y0, y1], autorange=False)
    fig.update_yaxes(separatethousands=True, exponentformat="none", showexponent="none")
    return fig
