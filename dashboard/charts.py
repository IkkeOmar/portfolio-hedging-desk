"""The dashboard's charts.

Every figure is built from a file the repository already writes, so a chart
cannot claim a number the code did not produce. The one exception is the
equity curve, which comes from ``reports/equity.csv`` -- written by the same
run as the report, and checked against it by the test suite.

Colours come from :mod:`dashboard.style`, so a figure matches the page it
sits on in both light and dark mode.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from .style import palette


def template():
    """A plotly template built from the current palette.

    Built as a ``go.layout.Template`` rather than registered globally: the
    global registry would be shared state, and two figures on the same page
    must not fight over it.
    """
    p = palette()
    return go.layout.Template(layout={
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Inter, Segoe UI, -apple-system, sans-serif",
                 "size": 12, "color": p["muted"]},
        "title": {"font": {"size": 13, "color": p["text"]}, "x": 0, "xanchor": "left"},
        "margin": {"l": 8, "r": 8, "t": 34, "b": 8},
        "xaxis": {
            "gridcolor": p["grid"], "zerolinecolor": p["grid"],
            "linecolor": p["line"], "tickfont": {"color": p["muted"], "size": 11},
            "title": {"font": {"color": p["muted"], "size": 11}},
            "showspikes": False,
        },
        "yaxis": {
            "gridcolor": p["grid"], "zerolinecolor": p["grid"],
            "linecolor": p["line"], "tickfont": {"color": p["muted"], "size": 11},
            "title": {"font": {"color": p["muted"], "size": 11}},
        },
        "legend": {
            "orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1,
            "font": {"color": p["muted"], "size": 11},
            "bgcolor": "rgba(0,0,0,0)",
        },
        "hoverlabel": {"bgcolor": p["surface"], "bordercolor": p["line"],
                       "font": {"color": p["text"], "family": "Inter, Segoe UI, sans-serif"}},
        "colorway": [p["hedged"], p["unhedged"], p["accent"], p["violet"], p["warn"]],
    })


def _rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB + alpha -> rgba(), so a fill can fade with the theme."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _base(title: str, height: int = 380) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(template=template(), title=dict(text=title), height=height,
                      hovermode="x unified")
    return fig


# ------------------------------------------------------------------ equity
def equity_figure(frame, windows: list[Any] | None = None, log_scale: bool = True,
                   height: int = 420) -> go.Figure:
    """Hedged against unhedged, on the same money."""
    p = palette()
    fig = _base("Growth of 1 unit, hedged against unhedged", height)
    fig.add_trace(go.Scatter(
        x=frame["date"], y=frame["unhedged_equity"], name="Unhedged",
        line=dict(color=p["unhedged"], width=1.6, dash="dot"),
        hovertemplate="unhedged  %{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=frame["date"], y=frame["hedged_equity"], name="Hedged",
        line=dict(color=p["hedged"], width=2.2),
        hovertemplate="hedged  %{y:.3f}<extra></extra>",
    ))
    if log_scale:
        fig.update_yaxes(type="log")
    fig.update_yaxes(title="equity (log)" if log_scale else "equity")
    for window in windows or []:
        try:
            start = window[0]
        except Exception:
            continue
        fig.add_vline(x=start, line=dict(color=p["line"], width=1, dash="dot"))
    return fig


def drawdown_figure(frame) -> go.Figure:
    """The underwater plot: how far below its peak the equity was."""
    p = palette()
    fig = _base("Drawdown from peak", 320)
    fig.add_trace(go.Scatter(
        x=frame["date"], y=frame["unhedged_drawdown"], name="Unhedged",
        line=dict(color=p["unhedged"], width=1.3),
        hovertemplate="unhedged  %{y:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=frame["date"], y=frame["hedged_drawdown"], name="Hedged",
        line=dict(color=p["hedged"], width=2.0),
        fill="tozeroy", fillcolor=_rgba(p["hedged"], 0.10),
        hovertemplate="hedged  %{y:.1%}<extra></extra>",
    ))
    fig.update_yaxes(title="drawdown", tickformat=".0%")
    return fig


def dial_figure(frame) -> go.Figure:
    """The dial over time: how much market risk the desk wanted to remove.

    The dial is only defined on the days the desk actually took a decision
    -- it is a **monthly** series, 172 observations spread over 3915
    trading days. Plotted on the daily axis it is NaN everywhere else,
    and a line through NaN gaps draws nothing at all: the chart renders
    as an empty grid. So it is plotted on its own dates, as a step
    function, because that is what it is -- a value that holds until the
    next decision.

    The markers are coloured by the regime the decision was taken in,
    which is where the interesting part is: the dial jumps when the
    market turns.
    """
    p = palette()
    if "dial" not in frame.columns:
        return _base("The dial: no dial series in the equity file", 300)

    observed = frame.dropna(subset=["dial"])
    if observed.empty:
        return _base("The dial: the desk took no decisions", 300)

    fig = _base(
        f"The dial: how much market risk to remove "
        f"({len(observed)} decision days)", 300
    )

    regime_colours = {"up": p["unhedged"], "down": p["warn"]}
    for regime, colour in regime_colours.items():
        if "regime" not in observed.columns:
            continue
        part = observed[observed["regime"] == regime]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part["date"], y=part["dial"], name=f"decided in a {regime} market",
            mode="markers", marker=dict(color=colour, size=4),
            hovertemplate=f"{regime}: dial %{{y:.2f}}<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        x=observed["date"], y=observed["dial"], name="dial",
        mode="lines", line=dict(color=p["accent"], width=1.6, shape="hv"),
        hovertemplate="dial  %{y:.2f}<extra></extra>",
    ))
    fig.update_yaxes(title="dial", range=[0, 1])
    fig.update_xaxes(title="")
    return fig


# ------------------------------------------------------------------ vetoes
def veto_figure(vetoes: list[dict[str, Any]]) -> go.Figure:
    """Vetoes per year, and which limit did the refusing."""
    p = palette()
    fig = _base("What the Risk seat refused, and when", 320)
    if not vetoes:
        return fig
    years = sorted({str(v.get("date", ""))[:4] for v in vetoes})
    counts = [sum(1 for v in vetoes if str(v.get("date", "")).startswith(y)) for y in years]
    fig.add_trace(go.Bar(
        x=years, y=counts, name="vetoes",
        marker=dict(color=p["warn"], line=dict(width=0)),
        hovertemplate="%{x}: %{y} vetoes<extra></extra>",
    ))
    fig.update_yaxes(title="vetoes", rangemode="tozero")
    fig.update_xaxes(title="")
    return fig


def veto_stage_figure(vetoes: list[dict[str, Any]]) -> go.Figure:
    """Which limit was hit."""
    p = palette()
    fig = _base("Which limit did the refusing", 260)
    if not vetoes:
        return fig
    stages: dict[str, int] = {}
    for v in vetoes:
        stage = str(v.get("stage", "unknown"))
        stages[stage] = stages.get(stage, 0) + 1
    items = sorted(stages.items(), key=lambda kv: -kv[1])
    fig.add_trace(go.Bar(
        x=[k for k, _ in items], y=[v for _, v in items], name="vetoes",
        marker=dict(color=p["bad"], line=dict(width=0)),
        orientation="v",
        hovertemplate="%{x}: %{y}<extra></extra>",
    ))
    fig.update_yaxes(title="vetoes", rangemode="tozero")
    return fig


# ------------------------------------------------------------------ trades
def cost_figure(trades: list[dict[str, Any]]) -> go.Figure:
    """What the hedging cost, and when."""
    p = palette()
    fig = _base("Cumulative cost of hedging", 320)
    if not trades:
        return fig
    dates = [str(t.get("date", "")) for t in trades]
    costs = [float(t.get("cost", 0.0)) for t in trades]
    running = []
    total = 0.0
    for c in costs:
        total += c
        running.append(total)
    fig.add_trace(go.Scatter(
        x=dates, y=running, name="cumulative cost",
        line=dict(color=p["bad"], width=2, shape="hv"),
        hovertemplate="%{y:,.2f}<extra></extra>",
    ))
    fig.update_yaxes(title="cumulative cost", rangemode="tozero")
    fig.update_xaxes(title="")
    return fig


# ------------------------------------------------------------- walkforward
def walkforward_figure(walkforward: list[dict[str, Any]]) -> go.Figure:
    """Sharpe by out-of-sample window."""
    p = palette()
    fig = _base("Sharpe by out-of-sample window", 300)
    if not walkforward:
        return fig
    labels = []
    for w in walkforward:
        window = w.get("window") or []
        labels.append(f"{window[0]} → {window[-1]}" if len(window) >= 2 else str(window))
    values = [float(w.get("sharpe", 0.0)) for w in walkforward]
    colours = [p["good"] if v > 0 else p["bad"] for v in values]
    fig.add_trace(go.Bar(
        x=labels, y=values, name="Sharpe",
        marker=dict(color=colours, line=dict(width=0)),
        hovertemplate="%{x}<br>Sharpe %{y:.3f}<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=p["line"], width=1))
    fig.update_yaxes(title="Sharpe")
    fig.update_xaxes(title="", tickangle=-20)
    return fig


# -------------------------------------------------------------------- gate
def r2_figure(r_squared: float, threshold: float) -> go.Figure:
    """Gate 1 as a gauge: measured R^2 against the 25% guideline."""
    p = palette()
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=float(r_squared),
        number={"suffix": "", "valueformat": ".1%", "font": {"size": 34, "color": p["text"]}},
        delta={"reference": float(threshold), "valueformat": ".1%",
               "relative": False, "position": "bottom",
               "font": {"size": 12, "color": p["muted"]}},
        gauge={
            "axis": {"range": [0, max(0.8, float(r_squared) * 1.2)], "tickcolor": p["line"],
                     "tickfont": {"color": p["muted"], "size": 10}},
            "bar": {"color": p["good"] if r_squared >= threshold else p["bad"]},
            "bgcolor": "rgba(0,0,0,0)",
            "borderwidth": 0,
            "threshold": {"line": {"color": p["violet"], "width": 3},
                          "thickness": 0.8, "value": float(threshold)},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(template=template(), height=230, margin=dict(l=8, r=8, t=10, b=10))
    return fig
