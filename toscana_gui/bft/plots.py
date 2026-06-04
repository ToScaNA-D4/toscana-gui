from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_bft_animation_figure(
    r: np.ndarray,
    pcf_iter: list[np.ndarray],
    pdf_iter: list[np.ndarray],
    *,
    iteration: int,
    context_id: str = "",
    width: int = 800,
    height: int = 600,
) -> go.Figure:
    r = np.asarray(r, dtype=float)
    n_frames = min(len(pcf_iter), len(pdf_iter))
    if n_frames <= 0:
        return go.Figure()

    # Ensure stable ordering.
    r_order = np.argsort(r) if r.size else np.arange(r.size)
    r_sorted = r[r_order]

    def _ypcf(i: int) -> np.ndarray:
        y = np.asarray(pcf_iter[i], dtype=float)
        return y[r_order] if y.shape == r.shape else y

    def _yr(i: int) -> np.ndarray:
        y = np.asarray(pdf_iter[i], dtype=float)
        return y[r_order] if y.shape == r.shape else y

    idx = max(0, min(int(iteration), n_frames - 1))
    n_last = n_frames - 1

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Pair Correlation Function  G(R)", "Pair Distribution Function  g(R)"),
        horizontal_spacing=0.08,
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=_ypcf(idx),
            mode="lines",
            line={"width": 2.0, "color": "rgba(37, 99, 235, 0.90)"},
            name="G(R)",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=r_sorted,
            y=_yr(idx),
            mode="lines",
            line={"width": 2.0, "color": "rgba(37, 99, 235, 0.90)"},
            name="g(R)",
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        title=None,
        margin=dict(l=40, r=20, t=60, b=40),
        hovermode="x unified",
        # Keep a stable uirevision per context so user pan/zoom doesn't reset
        # as they scrub through iterations using the Panel Player widget.
        uirevision=f"bft-anim:{context_id}" if context_id else "bft-anim",
        transition={"duration": 0},
        width=int(width),
        height=int(height),
        autosize=False,
        showlegend=False,
    )
    fig.update_xaxes(title_text="R", row=1, col=1)
    fig.update_yaxes(title_text="G(R)", row=1, col=1, separatethousands=True, exponentformat="none", showexponent="none")
    fig.update_xaxes(title_text="R", row=1, col=2)
    fig.update_yaxes(title_text="g(R)", row=1, col=2, separatethousands=True, exponentformat="none", showexponent="none")
    return fig


def build_bft_placeholder_figure(*, width: int = 800, height: int = 600) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        width=int(width),
        height=int(height),
        autosize=False,
        margin=dict(l=40, r=20, t=60, b=40),
        xaxis_visible=False,
        yaxis_visible=False,
        showlegend=False,
        uirevision="bft-placeholder",
    )
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text="No Back-FT results yet.",
        showarrow=False,
        font=dict(size=13, color="rgba(0,0,0,0.55)"),
    )
    return fig
