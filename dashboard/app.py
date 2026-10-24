"""The dashboard.

Run it from the repository root:

    streamlit run dashboard/app.py

What it shows is what the desk actually did: the headline numbers from
``reports/evaluation.json``, the equity path from ``reports/equity.csv``,
every veto with its reason, every trade, the out-of-sample windows, and one
trading day replayed seat by seat.

It is a viewer first. The one thing it can *do* is re-run the backtest and
run a single day with an LLM-backed judge -- and the second needs an API
key, which you set in the Settings tab and which never leaves this machine.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import charts, data, keys, style  # noqa: E402
from src.evaluation.gates import GATE_ORDER  # noqa: E402

st.set_page_config(
    page_title="Portfolio Hedging Desk",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="expanded",
    # These are the only three keys Streamlit's menu accepts (verified in
    # streamlit/commands/page_config.py). The Deploy button has no key and
    # is hidden by CSS instead.
    menu_items={"Get help": None, "Report a Bug": None, "About": None},
)

style.apply()

P = style.palette()

# Widget keys. Referenced by the test suite, so they live in one place:
# Streamlit's test harness addresses widgets by key, and a renamed button
# must fail the test loudly rather than silently test the wrong thing.
K_CONFIG = "w_config"
K_BACKTEST = "w_backtest"
K_PROVIDER = "w_provider"
K_API_KEY = "w_api_key"
K_SAVE = "w_save"
K_TEST = "w_test"
K_DAY = "w_day"
# The session-state key for the last desk run. It MUST NOT be the same
# string as K_DAY. A widget's key puts the widget's own value into
# session_state, so sharing a name means the app's stored output is
# overwritten by the widget's value on the next run -- and unpacking a
# date string as (chosen, output) raises. Two names, two jobs.
DESK_OUTPUT = "app_desk_output"
K_USE_LLM = "w_use_llm"
K_RUN_DAY = "w_run_day"
K_LOG = "w_log_scale"


# ---------------------------------------------------------------- helpers
def hero(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="hd-eyebrow">{eyebrow}</div>'
        f'<div class="hd-title">{title}</div>'
        f'<div class="hd-sub">{subtitle}</div>'
        f'<div class="hd-rule"></div>',
        unsafe_allow_html=True,
    )


def verdict_banner(payload: dict) -> None:
    passed = payload.get("verdict") == "pass"
    gate = payload.get("short_circuited_at")
    summary = payload.get("summary", {})
    mark = "✓" if passed else "✕"
    label = "GATE STACK PASSED" if passed else "GATE STACK FAILED"
    if passed:
        body = (
            "Every gate cleared. The hedge reduced risk at a cost that was "
            "worth paying, and the result held up out of sample."
        )
    else:
        body = (
            f"The stack stopped at <b>{gate}</b>. The hedging-equation R² is "
            f"{summary.get('r_squared', 0):.1%} against a 25% guideline, so there "
            "was something to hedge -- but the <i>timing</i> signal could not be "
            "distinguished from noise, so the desk is not allowed to claim it "
            "knows when to hedge. The gates short-circuit on purpose: a system "
            "that keeps going after a gate fails is a system that reports what "
            "it wants to hear."
        )
    st.markdown(
        f'<div class="hd-verdict {"pass" if passed else "fail"}">'
        f'<div class="hd-verdict-mark">{mark}</div>'
        f'<div><div class="hd-verdict-label">{label}</div>'
        f'<div class="hd-verdict-title">{gate or "all four gates"}</div>'
        f'<div class="hd-verdict-body">{body}</div></div></div>',
        unsafe_allow_html=True,
    )


def fmt_metric(key: str, value) -> str:
    """Render one gate metric for a human.

    The raw JSON holds full float precision -- ``0.5850042453516432`` --
    which is right for a machine and wrong for a card. The formatting is
    driven by the key's *meaning*, not by the magnitude of the value, so a
    new gate cannot silently print a proportion as if it were a percentage.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return f"{value:,}"
    v = float(value)
    if key.endswith("_pct"):
        # Already in percentage points: 35.58 means 35.58%.
        return f"{v:.1f}%"
    if "tstat" in key:
        return f"{v:.2f}"
    if key == "r_squared" or "threshold" in key or key.startswith("ic_"):
        # A proportion between 0 and 1.
        return f"{v:.1%}" if abs(v) >= 0.001 else f"{v:.2%}"
    if abs(v) < 1:
        return f"{v:.4g}"
    return f"{v:,.4g}"


def metric_card(label: str, hedged: str, unhedged: str, chip: str,
                good: bool | None) -> None:
    """A headline number with its comparison to the unhedged portfolio.

    ``good`` decides the chip's colour and is passed in rather than derived
    from the numbers, because "is this better?" has a different answer for
    volatility and drawdown than it does for return: a drawdown of -47% is
    *better* than -62%, and an arrow would say the opposite.
    """
    if good is None:
        chip_html = f'<span class="hd-chip flat">{chip}</span>'
    else:
        chip_html = f'<span class="hd-chip {"good" if good else "bad"}">{chip}</span>'
    st.markdown(
        f'<div class="hd-card"><div class="hd-card-label">{label}</div>'
        f'<div class="hd-card-value">{hedged}</div>'
        f'<div class="hd-card-foot">{chip_html}'
        f'<span>unhedged {unhedged}</span></div></div>',
        unsafe_allow_html=True,
    )


def gate_card(gate: dict, pending: bool = False) -> None:
    if pending:
        st.markdown(
            '<div class="hd-gate pending"><div class="hd-gate-head">'
            f'<span class="hd-gate-name">{gate}</span>'
            '<span class="hd-badge pending">NOT REACHED</span></div>'
            '<div class="hd-gate-headline">Never ran</div>'
            '<div class="hd-gate-note">The gate stack stops at the first '
            "failure, so this gate was never evaluated. A gate that did not "
            "run is not a gate that passed.</div></div>",
            unsafe_allow_html=True,
        )
        return

    passed = bool(gate.get("passed"))
    metrics = gate.get("metrics") or {}
    notes = gate.get("notes") or []
    badge = "pass" if passed else "fail"
    rows = "".join(
        f'<div class="hd-kv"><span class="hd-kv-k">{k}</span>'
        f'<span class="hd-kv-v">{fmt_metric(k, v)}</span></div>'
        for k, v in metrics.items()
        if k not in ("source",)
    )
    note = f'<div class="hd-gate-note">{notes[0]}</div>' if notes else ""
    source = metrics.get("source", "")
    src = f'<div class="hd-gate-src">{source}</div>' if source else ""
    st.markdown(
        f'<div class="hd-gate"><div class="hd-gate-head">'
        f'<span class="hd-gate-name">{gate.get("name", "")}</span>'
        f'<span class="hd-badge {badge}">{"PASS" if passed else "FAIL"}</span>'
        f'</div>'
        f'<div class="hd-gate-headline">{gate.get("headline", "")}</div>'
        f'{note}{rows}{src}</div>',
        unsafe_allow_html=True,
    )


def seat_card(name: str, body: str, kind: str = "") -> None:
    st.markdown(
        f'<div class="hd-seat {kind}"><div class="hd-seat-name">{name}</div>'
        f'<div class="hd-seat-body">{body}</div></div>',
        unsafe_allow_html=True,
    )


def pct(value, digits: int = 2, signed: bool = False) -> str:
    if value is None:
        return "n/a"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{f:+.{digits}%}" if signed else f"{f:.{digits}%}"


def num(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(
        '<div class="hd-side-title">Portfolio Hedging Desk</div>',
        unsafe_allow_html=True,
    )
    st.caption("Five seats · one veto · four gates")

    st.markdown("---")

    st.markdown('<div class="hd-side-title">Run</div>', unsafe_allow_html=True)
    config_choice = st.selectbox(
        "Configuration",
        ["examples/holdings.example.yaml", "examples/holdings.csv.example.yaml"],
        key=K_CONFIG,
        help="Which portfolio to run.",
    )
    run_clicked = st.button("Run the backtest", type="primary", key=K_BACKTEST,
                            width="stretch")

    if run_clicked:
        with st.spinner("Running the walk-forward backtest. This takes about 16 seconds."):
            ok, message = data.run_backtest(
                config_choice, "reports/journal_backtest", "reports"
            )
        if ok:
            st.success(message or "done")
            st.rerun()
        else:
            st.error(message)

    st.markdown("---")
    st.markdown('<div class="hd-side-title">Settings</div>', unsafe_allow_html=True)
    provider_name = st.selectbox("LLM provider", list(keys.PROVIDERS), key=K_PROVIDER)
    provider = dict(keys.PROVIDERS[provider_name])
    if provider_name.startswith("Custom"):
        provider["base_url"] = st.text_input("Base URL", value=provider["base_url"],
                                             placeholder="https://api.example.com/v1", key="w_custom_base_url")
        provider["model"] = st.text_input("Model", value=provider["model"],
                                          placeholder="model-name",
                                          key="w_custom_model")
    else:
        st.caption(f"`{provider['base_url']}` · `{provider['model']}`")

    env_file = data.REPO_ROOT / keys.ENV_FILE
    stored = keys.read_env(env_file)
    existing = stored.get(provider["api_key_env"], "") or os.environ.get(
        provider["api_key_env"], ""
    )
    key_input = st.text_input(
        f"{provider['api_key_env']}",
        value="",
        type="password",
        key=K_API_KEY,
        placeholder=keys.mask(existing) if existing else "not set",
        help="Stored in .env on this machine. .env is in .gitignore, so it cannot be committed.",
    )

    col_a, col_b = st.columns(2)
    save_clicked = col_a.button("Save", key=K_SAVE, width="stretch")
    test_clicked = col_b.button("Test", key=K_TEST, width="stretch")

    effective_key = key_input or existing
    if save_clicked and key_input:
        keys.write_env_value(env_file, provider["api_key_env"], key_input)
        st.success(f"Saved to {keys.ENV_FILE}")
    if test_clicked:
        with st.spinner("Contacting the provider..."):
            ok, message = keys.test_connection(
                provider["base_url"], provider["model"], effective_key
            )
        if ok:
            st.success(message)
        else:
            st.error(message)

    st.markdown("---")
    st.caption(
        "The desk needs **no key at all**. The default judge is deterministic, "
        "and the whole dashboard runs offline."
    )


# ------------------------------------------------------------------ header
hero(
    "A hedge is a trade in risk, not a trade in profit",
    "Portfolio Hedging Desk",
    "Five seats around a table. One of them can say no, and nothing trades "
    "without its signature. Every decision is written to a journal before the "
    "outcome is known -- and the gates decide whether the result means "
    "anything.",
)

payload = data.load_report()
equity = data.load_equity()

if payload is None:
    st.warning(
        "No evaluation report yet. Press **Run the backtest** in the sidebar, "
        "or run `python scripts/backtest.py` from the repository root."
    )
    st.stop()

summary = payload.get("summary", {})
gates = payload.get("gates", [])


# -------------------------------------------------------------------- tabs
tab_overview, tab_risk, tab_desk, tab_activity, tab_wf, tab_settings = st.tabs(
    ["Overview", "Risk", "Desk", "Vetoes & trades", "Walk-forward", "Settings"]
)


# --- Overview ---------------------------------------------------------------
with tab_overview:
    verdict_banner(payload)

    st.markdown('<div class="hd-label">Hedged against unhedged</div>',
                unsafe_allow_html=True)
    cards = [
        ("CAGR", pct(summary.get("hedged_cagr"), signed=True),
         pct(summary.get("unhedged_cagr"), signed=True), "cagr"),
        ("Sharpe", num(summary.get("hedged_sharpe")),
         num(summary.get("unhedged_sharpe")), "sharpe"),
        ("Volatility", pct(summary.get("hedged_annualised_vol")),
         pct(summary.get("unhedged_annualised_vol")), "vol"),
        ("Max drawdown", pct(summary.get("hedged_max_drawdown")),
         pct(summary.get("unhedged_max_drawdown")), "dd"),
    ]
    for col, (label, hedged, unhedged, kind) in zip(st.columns(4), cards):
        with col:
            if kind == "cagr":
                d = summary["hedged_cagr"] - summary["unhedged_cagr"]
                chip = f"{abs(d) * 100:.2f} pp {'higher' if d >= 0 else 'lower'}"
                good = d > 0
            elif kind == "sharpe":
                d = summary["hedged_sharpe"] - summary["unhedged_sharpe"]
                chip = f"{abs(d):.3f} {'higher' if d >= 0 else 'lower'}"
                good = d > 0
            elif kind == "vol":
                d = (summary["hedged_annualised_vol"]
                     - summary["unhedged_annualised_vol"])
                chip = f"{abs(d) * 100:.2f} pp {'lower' if d <= 0 else 'higher'}"
                good = d < 0
            else:
                d = (abs(summary["hedged_max_drawdown"])
                     - abs(summary["unhedged_max_drawdown"]))
                chip = f"{abs(d) * 100:.1f} pp {'shallower' if d <= 0 else 'deeper'}"
                good = d < 0
            metric_card(label, hedged, unhedged, chip, good)

    st.markdown("")
    if equity is not None:
        st.plotly_chart(
            charts.equity_figure(equity, payload.get("walkforward"), height=330),
            width="stretch",
        )

    st.markdown('<div class="hd-label">The gate stack</div>', unsafe_allow_html=True)
    ran = {g.get("name") for g in gates}
    not_run = [name for name in GATE_ORDER if name not in ran]
    st.caption(
        f"{len(gates)} of {len(GATE_ORDER)} gates ran. "
        + ("The stack stops at the first failure, so the rest were never "
           "evaluated." if not_run else "Every gate was evaluated.")
    )
    for col, name in zip(st.columns(len(GATE_ORDER)), GATE_ORDER):
        with col:
            match = next((g for g in gates if g.get("name") == name), None)
            gate_card(match if match is not None else name, pending=match is None)

    st.markdown("")
    n_veto = summary.get("n_vetoes", 0)
    n_prop = summary.get("n_proposals", 0)
    st.markdown(
        f'<div class="hd-note">'
        f"<b>{summary.get('n_days', 0):,}</b> trading days · "
        f"<b>{summary.get('n_trades', 0)}</b> trades · "
        f"<b>{n_prop}</b> proposals of which the Risk seat refused "
        f"<b>{n_veto}</b> "
        f"({(100 * n_veto / n_prop if n_prop else 0):.1f}%) · "
        f"costs <b>{summary.get('total_cost', 0):,.2f}</b> charged · "
        f"<b>{summary.get('n_seat_errors', 0)}</b> seat errors · "
        f"<b>{summary.get('trials_declared', 1)}</b> variant tried." 
        "</div>",
        unsafe_allow_html=True,
    )


# --- Risk -------------------------------------------------------------------
with tab_risk:
    if equity is None:
        st.info("No `reports/equity.csv` yet. Re-run the backtest to produce it.")
    else:
        log_scale = st.toggle("Log scale", value=True, key=K_LOG,
                              help="Log scale makes the relative gap visible.")
        st.plotly_chart(charts.equity_figure(equity, payload.get("walkforward"),
                                              log_scale=log_scale),
                        width="stretch")
        left, right = st.columns([3, 2])
        with left:
            st.plotly_chart(charts.drawdown_figure(equity), width="stretch")
        with right:
            st.plotly_chart(charts.dial_figure(equity), width="stretch")
        st.markdown(
            '<div class="hd-note">The hedged curve is the teal one. The gap '
            "between the two curves is the risk that was removed; the cost is "
            "the price of removing it, and it is already deducted from the "
            "hedged curve. The dial is decided monthly, so it is drawn as a "
            "step over the decision days only -- a line through the gaps "
            "would be a chart with nothing in it.</div>",
            unsafe_allow_html=True,
        )


# --- Desk -------------------------------------------------------------------
with tab_desk:
    st.markdown('<div class="hd-label">One trading day, seat by seat</div>',
                unsafe_allow_html=True)
    try:
        dates = data.available_dates()
    except Exception as exc:  # noqa: BLE001
        dates = []
        st.caption(f"Could not list trading days: {exc}")

    if dates:
        left, right = st.columns([2, 3])
        with left:
            chosen = st.selectbox("Trading day", dates, index=0, key=K_DAY)
        with right:
            use_llm = st.toggle(
                "Use an LLM judge instead of the deterministic one",
                value=False, key=K_USE_LLM,
                help="Needs an API key. Set one in the sidebar. Three votes are "
                     "taken and the majority wins, exactly as with the "
                     "deterministic judge.",
            )
            judge = None
            if use_llm:
                key = os.environ.get(provider["api_key_env"], "") or stored.get(
                    provider["api_key_env"], ""
                )
                if not key:
                    st.warning("No API key for that provider. Set one in the sidebar.")
                else:
                    os.environ[provider["api_key_env"]] = key
                    judge = keys.judge_from_env(provider)

        if st.button("Run this day", type="primary", key=K_RUN_DAY):
            with st.spinner("Running the five seats..."):
                try:
                    out = data.run_desk_day(config_choice, chosen,
                                            "reports/journal_desk", judge=judge)
                except Exception as exc:  # noqa: BLE001
                    st.error(f"The desk raised: {type(exc).__name__}: {exc}")
                    out = None
            if out:
                st.session_state[DESK_OUTPUT] = (chosen, out)
                st.rerun()

    if DESK_OUTPUT in st.session_state:
        chosen, out = st.session_state[DESK_OUTPUT]
        result = out["result"]
        st.markdown(
            f'<div class="hd-note">Desk run for <b>{chosen}</b>. Information '
            f"cutoff {result.get('information_cutoff', 'n/a')}.</div>",
            unsafe_allow_html=True,
        )
        for seat, payload_seat in (result.get("seats") or {}).items():
            if isinstance(payload_seat, dict):
                body = "<br>".join(
                    f"{k}: {v}" for k, v in payload_seat.items()
                    if k in ("hedge_symbol", "target_notional", "portfolio_beta",
                             "hedged_beta", "est_vol_reduction_pct", "est_cost_bps",
                             "reward_to_risk", "reason")
                )
            else:
                body = str(payload_seat)
            seat_card(seat.replace("_", " "), body or "no detail")

        verdicts = out.get("verdicts") or []
        if verdicts:
            st.markdown('<div class="hd-label">The judge\'s votes</div>',
                        unsafe_allow_html=True)
            for v in verdicts:
                kind = "approve" if str(v.get("verdict", "")).lower().startswith("appr") else "veto"
                seat_card(
                    f"judge vote {v.get('run', '')}".strip(),
                    f"<b>{v.get('verdict')}</b> · score {v.get('score')}"
                    f"<br>{'<br>'.join(v.get('reasons') or [])}",
                    kind=kind,
                )


# --- Vetoes & trades --------------------------------------------------------
with tab_activity:
    vetoes = payload.get("vetoes") or []
    trades = payload.get("trades") or []
    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(charts.veto_figure(vetoes), width="stretch")
    with right:
        st.plotly_chart(charts.veto_stage_figure(vetoes), width="stretch")

    st.markdown('<div class="hd-label">Every refusal, with its reason</div>',
                unsafe_allow_html=True)
    if vetoes:
        import pandas as pd

        st.dataframe(pd.DataFrame(vetoes), width="stretch", hide_index=True)
    else:
        st.caption("Nothing was refused on this run.")

    st.markdown('<div class="hd-label">What the hedging cost</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.cost_figure(trades), width="stretch")
    if trades:
        import pandas as pd

        st.dataframe(pd.DataFrame(trades), width="stretch", hide_index=True)


# --- Walk-forward -----------------------------------------------------------
with tab_wf:
    wf = payload.get("walkforward") or []
    st.plotly_chart(charts.walkforward_figure(wf), width="stretch")
    st.markdown(
        '<div class="hd-note">Each window is scored out of sample, in time. '
        "This is the only out-of-sample evidence in the repository: the "
        "<i>portfolio</i> is the same one throughout, which is why the "
        "survivorship caveat in the README matters.</div>",
        unsafe_allow_html=True,
    )
    if wf:
        import pandas as pd

        # The window is a list in the report; Arrow cannot hold a list
        # column, so it is flattened into columns a reader can sort by.
        rows = []
        for w in wf:
            window = w.get("window") or []
            rows.append({
                "from": window[0] if len(window) > 0 else "",
                "to": window[1] if len(window) > 1 else "",
                "observations": window[2] if len(window) > 2 else "",
                "Sharpe": w.get("sharpe"),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# --- Settings ---------------------------------------------------------------
with tab_settings:
    st.markdown('<div class="hd-label">API keys</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hd-note">The dashboard and the desk run with '
        "<b>no key at all</b>. The default Judge seat is deterministic: three "
        "identical votes, aggregated by majority. A key is only needed if you "
        "want to swap in an LLM-backed judge and watch a model's opinion "
        "differ from the rule-based one.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")

    rows = []
    for name, spec in keys.PROVIDERS.items():
        value = stored.get(spec["api_key_env"], "")
        rows.append({
            "provider": name,
            "environment variable": spec["api_key_env"],
            "base URL": spec["base_url"] or "(custom)",
            "model": spec["model"] or "(custom)",
            "key": keys.mask(value) if value else "not set",
        })
    import pandas as pd

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.markdown('<div class="hd-label">Where the key goes</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hd-note">Keys are written to <b>.env</b> in the '
        "repository root. That file is listed in <b>.gitignore</b>, so it "
        "cannot be committed by accident, and the dashboard never renders a "
        "key, never writes one into the evaluation report, and never puts one "
        "in the journal. A provider error message is scrubbed of the key "
        "before it is shown.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("")
    st.markdown('<div class="hd-label">What the key is used for</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="hd-note">Exactly one thing: the Judge seat. The other '
        "four seats -- Scan, Quant, Hedger and Risk -- are arithmetic. The "
        "hedge ratio, the position size and the risk limits are never chosen "
        "by a model, and whether the strategy worked is decided by the gates, "
        "which are arithmetic too.</div>",
        unsafe_allow_html=True,
    )
