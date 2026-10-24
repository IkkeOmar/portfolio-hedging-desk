"""The dashboard's visual language.

Streamlit's own theme handles colours, fonts and radii. What it does not do
is make an app look *designed* -- so this module adds the parts a theme
cannot: a hero header, bordered metric cards, a verdict banner that reads
at a glance, and consistent chart styling.

The palette is mode-aware. Streamlit can switch between light and dark from
its settings menu, and that switch re-runs the script, so the CSS is
re-emitted with the matching palette each time. That is why nothing here
hard-codes a colour that only works on one background.
"""

from __future__ import annotations

# --- palettes -------------------------------------------------------------
# Two keys per colour: the fill used on a dark surface and on a light one.
# A colour that passes contrast on one background usually fails on the
# other, so they are not interchangeable.

DARK = {
    "bg": "#0B1220",
    "surface": "#141E33",
    "surface_2": "#1B2740",
    "line": "#27344F",
    "text": "#E6EDF7",
    "muted": "#8FA3C0",
    "accent": "#22D3EE",
    "hedged": "#2DD4BF",
    "unhedged": "#7C8CA5",
    "good": "#34D399",
    "good_ink": "#6EE7B7",
    "bad": "#FB7185",
    "bad_ink": "#FDA4AF",
    "warn": "#FBBF24",
    "warn_ink": "#FCD34D",
    "violet": "#A78BFA",
    "grid": "rgba(255,255,255,0.07)",
    "shadow": "0 1px 2px rgba(0,0,0,0.35), 0 8px 24px rgba(0,0,0,0.22)",
}

LIGHT = {
    "bg": "#F5F7FB",
    "surface": "#FFFFFF",
    "surface_2": "#EEF2F8",
    "line": "#DCE3ED",
    "text": "#0F172A",
    "muted": "#5A6B85",
    "accent": "#0E7490",
    "hedged": "#0F766E",
    "unhedged": "#64748B",
    "good": "#059669",
    "good_ink": "#047857",
    "bad": "#E11D48",
    "bad_ink": "#BE123C",
    "warn": "#B45309",
    "warn_ink": "#92400E",
    "violet": "#6D28D9",
    "grid": "rgba(15,23,42,0.08)",
    "shadow": "0 1px 2px rgba(15,23,42,0.05), 0 8px 24px rgba(15,23,42,0.06)",
}


def is_dark() -> bool:
    """Is Streamlit currently in dark mode?

    ``st.context.theme.type`` is "light" or "dark" inside a running app. It
    is None in bare mode (a plain ``python`` import), so the default is
    dark -- which is what the theme in config.toml sets.
    """
    try:
        import streamlit as st

        return (st.context.theme.type or "dark") == "dark"
    except Exception:
        return True


def palette() -> dict[str, str]:
    return DARK if is_dark() else LIGHT


def css() -> str:
    """The stylesheet for the current colour scheme."""
    p = palette()
    return f"""
<style>
  :root {{
    --hd-bg: {p['bg']};
    --hd-surface: {p['surface']};
    --hd-surface-2: {p['surface_2']};
    --hd-line: {p['line']};
    --hd-text: {p['text']};
    --hd-muted: {p['muted']};
    --hd-accent: {p['accent']};
    --hd-hedged: {p['hedged']};
    --hd-unhedged: {p['unhedged']};
    --hd-good: {p['good']};
    --hd-good-ink: {p['good_ink']};
    --hd-bad: {p['bad']};
    --hd-bad-ink: {p['bad_ink']};
    --hd-warn: {p['warn']};
    --hd-warn-ink: {p['warn_ink']};
    --hd-shadow: {p['shadow']};
  }}

  /* Streamlit's own header is 56px tall and floats over the content.
     Without this much top padding the first line of the hero sat under it
     and was half-covered. */
  .block-container {{ padding-top: 4.1rem; padding-bottom: 3.5rem; max-width: 1500px; }}

  /* The Deploy button and the main menu are Streamlit chrome, not part of
     this product. Hiding them is what stops a screenshot of this dashboard
     from looking like a screenshot of a demo. */
  [data-testid="stAppDeployButton"],
  [data-testid="stMainMenu"] {{ display: none; }}
  [data-testid="stHeader"] {{ background: transparent; }}

  /* ---------------- hero ---------------- */
  .hd-eyebrow {{
    font-size: 0.66rem; letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--hd-accent); font-weight: 700; margin-bottom: 0.35rem;
  }}
  .hd-title {{
    font-size: 2.05rem; font-weight: 640; letter-spacing: -0.022em;
    line-height: 1.15; margin: 0 0 0.4rem 0; color: var(--hd-text);
  }}
  .hd-sub {{
    font-size: 0.97rem; line-height: 1.55; color: var(--hd-muted);
    max-width: 74ch; margin: 0;
  }}
  .hd-rule {{
    height: 2px; border-radius: 2px; margin: 1.15rem 0 1.5rem 0;
    background: linear-gradient(90deg, var(--hd-accent) 0%, transparent 72%);
  }}

  /* ---------------- verdict banner ---------------- */
  .hd-verdict {{
    border-radius: 15px; padding: 1.05rem 1.25rem; border: 1px solid;
    display: flex; gap: 1.1rem; align-items: flex-start;
    box-shadow: var(--hd-shadow);
  }}
  .hd-verdict.fail {{
    background: color-mix(in srgb, var(--hd-bad) 11%, var(--hd-surface));
    border-color: color-mix(in srgb, var(--hd-bad) 42%, transparent);
  }}
  .hd-verdict.pass {{
    background: color-mix(in srgb, var(--hd-good) 11%, var(--hd-surface));
    border-color: color-mix(in srgb, var(--hd-good) 42%, transparent);
  }}
  .hd-verdict .hd-verdict-mark {{
    font-size: 1.6rem; line-height: 1; font-weight: 700; margin-top: 0.05rem;
  }}
  .hd-verdict.fail .hd-verdict-mark {{ color: var(--hd-bad-ink); }}
  .hd-verdict.pass .hd-verdict-mark {{ color: var(--hd-good-ink); }}
  .hd-verdict-label {{
    font-size: 0.66rem; letter-spacing: 0.18em; text-transform: uppercase;
    font-weight: 700; margin-bottom: 0.3rem;
  }}
  .hd-verdict.fail .hd-verdict-label {{ color: var(--hd-bad-ink); }}
  .hd-verdict.pass .hd-verdict-label {{ color: var(--hd-good-ink); }}
  .hd-verdict-title {{ font-size: 1.16rem; font-weight: 620; margin-bottom: 0.3rem; }}
  .hd-verdict-body {{ font-size: 0.92rem; line-height: 1.55; color: var(--hd-muted); }}

  /* ---------------- metric cards ---------------- */
  /* The cards carry their own comparison chip, because "is this better?"
     has a different answer for volatility and drawdown than it does for
     return. A shared up-arrow would lie half the time. */
  .hd-card {{
    background: var(--hd-surface);
    border: 1px solid var(--hd-line);
    border-radius: 14px;
    padding: 0.85rem 1rem 0.9rem 1rem;
    box-shadow: var(--hd-shadow);
    height: 100%;
  }}
  .hd-card-label {{
    font-size: 0.66rem; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--hd-muted); font-weight: 650; margin-bottom: 0.3rem;
  }}
  .hd-card-value {{
    font-size: 1.72rem; font-weight: 640; letter-spacing: -0.022em;
    font-variant-numeric: tabular-nums; line-height: 1.1;
    color: var(--hd-text);
  }}
  .hd-card-foot {{
    margin-top: 0.5rem; font-size: 0.78rem; color: var(--hd-muted);
    display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;
  }}
  .hd-chip {{
    display: inline-block; padding: 0.1rem 0.42rem; border-radius: 6px;
    font-size: 0.72rem; font-weight: 700; font-variant-numeric: tabular-nums;
  }}
  .hd-chip.good {{ background: color-mix(in srgb, var(--hd-good) 17%, transparent); color: var(--hd-good-ink); }}
  .hd-chip.bad  {{ background: color-mix(in srgb, var(--hd-bad) 17%, transparent);  color: var(--hd-bad-ink); }}
  .hd-chip.flat {{ background: var(--hd-surface-2); color: var(--hd-muted); }}

  [data-testid="stMetric"] {{
    background: var(--hd-surface);
    border: 1px solid var(--hd-line);
    border-radius: 14px;
    padding: 0.9rem 1.05rem 0.95rem 1.05rem;
    box-shadow: var(--hd-shadow);
  }}
  [data-testid="stMetricLabel"] {{
    font-size: 0.68rem; letter-spacing: 0.13em; text-transform: uppercase;
    color: var(--hd-muted); font-weight: 600;
  }}
  [data-testid="stMetricValue"] {{
    font-variant-numeric: tabular-nums; letter-spacing: -0.01em;
  }}

  /* ---------------- gate cards ---------------- */
  .hd-gate {{
    background: var(--hd-surface); border: 1px solid var(--hd-line);
    border-radius: 14px; padding: 1rem 1.1rem; box-shadow: var(--hd-shadow);
    height: 100%;
  }}
  .hd-gate.pending {{ opacity: 0.62; border-style: dashed; box-shadow: none; }}
  .hd-gate.pending .hd-gate-headline {{ font-size: 1.05rem; color: var(--hd-muted); font-weight: 550; }}
  .hd-gate-head {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.55rem; }}
  .hd-gate-name {{ font-size: 0.95rem; font-weight: 620; flex: 1; }}
  .hd-badge {{
    display: inline-block; padding: 0.13rem 0.52rem; border-radius: 999px;
    font-size: 0.63rem; font-weight: 750; letter-spacing: 0.1em;
  }}
  .hd-badge.pass {{ background: color-mix(in srgb, var(--hd-good) 18%, transparent); color: var(--hd-good-ink); }}
  .hd-badge.fail {{ background: color-mix(in srgb, var(--hd-bad) 18%, transparent); color: var(--hd-bad-ink); }}
  .hd-badge.pending {{ background: var(--hd-surface-2); color: var(--hd-muted); }}
  .hd-gate-headline {{
    font-size: 1.45rem; font-weight: 650; font-variant-numeric: tabular-nums;
    margin-bottom: 0.3rem; letter-spacing: -0.01em;
  }}
  .hd-gate-note {{ font-size: 0.85rem; color: var(--hd-muted); line-height: 1.5; }}
  .hd-gate-src {{ font-size: 0.74rem; color: var(--hd-muted); margin-top: 0.55rem;
                  padding-top: 0.5rem; border-top: 1px solid var(--hd-line); }}

  /* ---------------- section label ---------------- */
  .hd-label {{
    font-size: 0.66rem; letter-spacing: 0.19em; text-transform: uppercase;
    color: var(--hd-muted); font-weight: 700; margin: 0.4rem 0 0.55rem 0;
  }}

  /* ---------------- seat cards (the desk tab) ---------------- */
  .hd-seat {{
    background: var(--hd-surface); border: 1px solid var(--hd-line);
    border-left: 3px solid var(--hd-accent);
    border-radius: 12px; padding: 0.85rem 1rem; margin-bottom: 0.6rem;
  }}
  .hd-seat.veto {{ border-left-color: var(--hd-bad); }}
  .hd-seat.approve {{ border-left-color: var(--hd-good); }}
  .hd-seat-name {{
    font-size: 0.67rem; letter-spacing: 0.16em; text-transform: uppercase;
    font-weight: 700; color: var(--hd-accent); margin-bottom: 0.28rem;
  }}
  .hd-seat.veto .hd-seat-name {{ color: var(--hd-bad-ink); }}
  .hd-seat.approve .hd-seat-name {{ color: var(--hd-good-ink); }}
  .hd-seat-body {{ font-size: 0.9rem; line-height: 1.5; }}

  /* ---------------- misc ---------------- */
  .hd-kv {{ display: flex; justify-content: space-between; gap: 1rem;
            font-size: 0.86rem; padding: 0.34rem 0;
            border-bottom: 1px solid var(--hd-line); }}
  .hd-kv:last-child {{ border-bottom: none; }}
  .hd-kv-k {{ color: var(--hd-muted); }}
  .hd-kv-v {{ font-variant-numeric: tabular-nums; font-weight: 600; }}

  [data-testid="stDataFrame"] {{
    border: 1px solid var(--hd-line); border-radius: 13px; overflow: hidden;
  }}
  [data-testid="stSidebar"] {{ border-right: 1px solid var(--hd-line); }}
  [data-testid="stSidebar"] hr {{ margin: 0.7rem 0; }}
  [data-testid="stSidebarUserContent"] {{ padding-top: 1.1rem; }}
  [data-testid="stSidebar"] .hd-side-title {{
    font-size: 0.68rem; letter-spacing: 0.18em; text-transform: uppercase;
    color: var(--hd-accent); font-weight: 700; margin-bottom: 0.15rem;
  }}
  [data-testid="stTabs"] button {{ font-weight: 560; }}
  .hd-note {{ font-size: 0.83rem; color: var(--hd-muted); line-height: 1.55; }}
  .hd-mono {{ font-variant-numeric: tabular-nums; }}
</style>
"""


def apply() -> None:
    """Emit the stylesheet into the page."""
    import streamlit as st

    st.markdown(css(), unsafe_allow_html=True)
