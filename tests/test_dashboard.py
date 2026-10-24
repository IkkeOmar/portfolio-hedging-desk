"""Test the dashboard the way a user would use it.

Two layers, because they catch different things:

* **This file** drives the app with Streamlit's own test harness
  (``streamlit.testing.v1.AppTest``). It renders the script, then
  *interacts with the widgets* -- clicking buttons, toggling switches,
  choosing a different trading day, typing an API key -- and asserts on
  what the app says afterwards. Every widget is addressed by its ``key``,
  so a renamed control fails here instead of silently testing the wrong
  thing.

* ``tests/test_dashboard_browser.py`` drives a real browser and really
  clicks the tabs. Streamlit's harness has no click method for
  ``st.tabs`` -- a tab is a container, not a widget -- so tab navigation
  can only be exercised in a browser.

The tests skip when Streamlit is not installed. Streamlit is an
*optional* extra: the core package and the core suite stay lean and
installable without it. The CI job that installs the extra runs this file
for real, so the skip never hides a broken dashboard in CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

AppTest = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit is an optional extra"
).AppTest

APP = REPO / "dashboard" / "app.py"
REPORT = REPO / "reports" / "evaluation.json"


@pytest.fixture(scope="module")
def rendered():
    """The app, rendered once, for the read-only assertions."""
    if not APP.exists():
        pytest.skip(f"no dashboard at {APP}")
    at = AppTest.from_file(str(APP), default_timeout=300)
    at.run()
    return at


@pytest.fixture
def fresh():
    """A brand-new instance, for tests that change widget state."""
    at = AppTest.from_file(str(APP), default_timeout=300)
    at.run()
    return at


def _no_exception(at) -> None:
    assert not at.exception, "\n".join(
        f"{exc.value}\n{exc.stack_trace}" for exc in at.exception
    )


def _body(at) -> str:
    """Everything the app rendered, as one searchable string."""
    parts = [m.value for m in at.markdown]
    parts += [c.value for c in at.caption]
    return "\n".join(parts)


# --------------------------------------------------------------- rendering
def test_the_dashboard_renders_without_raising(rendered):
    """The whole point: the first render must not blow up."""
    _no_exception(rendered)


def test_it_says_what_it_is(rendered):
    body = _body(rendered)
    assert "Portfolio Hedging Desk" in body
    assert "A hedge is a trade in risk" in body


def test_the_verdict_banner_is_prominent(rendered):
    """The honest null must be the first thing a reader sees."""
    body = _body(rendered)
    assert "GATE STACK FAILED" in body
    assert "regime_information" in body


def test_the_headline_numbers_are_shown(rendered):
    """Four cards: CAGR, Sharpe, volatility, max drawdown."""
    body = _body(rendered)
    for label in ("CAGR", "Sharpe", "Volatility", "Max drawdown"):
        assert f">{label}</div>" in body, f"missing the {label} card"
    # The comparison against the unhedged portfolio, not just the number.
    assert "unhedged" in body


def test_the_whole_gate_stack_is_shown(rendered):
    """All four gates, including the ones that never ran.

    The stack short-circuits at the first failure, so a report contains
    two gates on this run. The other two must still be on screen, marked
    as never evaluated -- otherwise the dashboard implies the desk only
    had two criteria.
    """
    body = _body(rendered)
    from src.evaluation.gates import GATE_ORDER

    for name in GATE_ORDER:
        assert name in body, f"gate {name} is not on the page"
    assert "NOT REACHED" in body
    assert "Never ran" in body


def test_the_gate_values_are_readable(rendered):
    """No raw float precision on a card."""
    body = _body(rendered)
    assert "0.5850042453516432" not in body
    assert "58.5%" in body


def test_every_tab_has_content(rendered):
    """Each tab panel holds something.

    Streamlit renders every tab panel eagerly, so an empty panel is a
    silent failure -- it looks fine until somebody clicks the tab.
    """
    assert len(rendered.tabs) == 6
    for index, tab in enumerate(rendered.tabs):
        assert len(tab.markdown) > 0, f"tab {index} ({tab.label}) is empty"


def test_the_activity_tables_are_there(rendered):
    """The veto table, the trade table and the walk-forward table."""
    assert len(rendered.dataframe) >= 3, (
        f"expected the veto, trade and walk-forward tables; "
        f"got {len(rendered.dataframe)}"
    )


def test_the_key_setup_is_reachable(rendered):
    """A reader has to be able to set the LLM judge's key from the UI."""
    labels = [i.label for i in rendered.sidebar.text_input]
    assert any("API_KEY" in label for label in labels), labels
    assert rendered.sidebar.button(key="w_save")
    assert rendered.sidebar.button(key="w_test")


# ------------------------------------------------------------- interaction
def test_the_log_scale_toggle_actually_toggles(fresh):
    """Flip the switch, and the app re-renders with it on."""
    fresh.toggle(key="w_log_scale").set_value(False).run()
    _no_exception(fresh)
    assert fresh.toggle(key="w_log_scale").value is False

    fresh.toggle(key="w_log_scale").set_value(True).run()
    _no_exception(fresh)
    assert fresh.toggle(key="w_log_scale").value is True


def test_choosing_a_trading_day_rerenders_cleanly(fresh):
    """Pick a different day; the app must not raise."""
    box = fresh.selectbox(key="w_day")
    assert len(box.options) > 1
    first = box.value
    box.set_value(box.options[1]).run()
    _no_exception(fresh)
    assert fresh.selectbox(key="w_day").value != first


def test_running_a_day_produces_the_seat_cards(fresh):
    """The Desk tab runs the real desk and shows what each seat said.

    This is the expensive one. It exercises the seat logic, the journal
    and the rendering path together.
    """
    fresh.button(key="w_run_day").click().run()
    _no_exception(fresh)
    body = _body(fresh)
    assert "Desk run for" in body
    for seat in ("quant", "scan", "hedger", "judge"):
        assert seat in body.lower(), f"no card for the {seat} seat"


def test_the_llm_judge_toggle_warns_when_there_is_no_key(fresh):
    """Turning on the LLM judge without a key must say so, not crash."""
    fresh.toggle(key="w_use_llm").set_value(True).run()
    _no_exception(fresh)
    warnings = [w.value for w in fresh.warning]
    assert any("API key" in w for w in warnings), warnings


def test_the_provider_selector_switches_the_key_field(fresh):
    """Choosing another provider changes which key is asked for."""
    fresh.sidebar.selectbox(key="w_provider").set_value("OpenAI").run()
    _no_exception(fresh)
    labels = [i.label for i in fresh.sidebar.text_input]
    assert "OPENAI_API_KEY" in labels, labels


def test_typing_a_key_never_echoes_it(fresh):
    """The key must not appear anywhere in the rendered output.

    It is a password field, but a password field is a UI hint, not a
    guarantee: if the value ever reached a markdown block, a caption or
    an error message, it would be in the page source.
    """
    # A value that cannot be mistaken for a real credential: no "sk-"
    # prefix, no provider format. A scanner should not flag this file.
    secret = "dummy-key-not-a-real-secret"
    fresh.sidebar.text_input(key="w_api_key").set_value(secret).run()
    _no_exception(fresh)
    assert secret not in _body(fresh), "the API key leaked into the page"


def test_a_failed_connection_test_reports_an_error_instead_of_raising(fresh):
    """A bad endpoint must produce a readable error, not a traceback.

    The endpoint is a local port with nothing listening on it, so this
    proves the error path without sending a request to a third party.
    """
    fresh.sidebar.selectbox(key="w_provider").set_value(
        "Custom (OpenAI-compatible)").run()
    _no_exception(fresh)
    fresh.sidebar.text_input(key="w_custom_base_url").set_value(
        "http://127.0.0.1:9/v1").run()
    fresh.sidebar.text_input(key="w_custom_model").set_value("test-model").run()
    fresh.sidebar.text_input(key="w_api_key").set_value("dummy-key-not-a-real-secret").run()
    fresh.sidebar.button(key="w_test").click().run()
    _no_exception(fresh)
    errors = [e.value for e in fresh.error]
    assert errors, "a failed connection test must report an error"


def test_running_the_backtest_reproduces_the_committed_report(fresh):
    """The button in the sidebar must regenerate the shipped report.

    This is the strongest reproducibility claim the repository makes: the
    numbers a reader sees in the README are the numbers the UI produces.
    """
    before = REPORT.read_bytes()
    fresh.sidebar.button(key="w_backtest").click().run()
    _no_exception(fresh)
    after = REPORT.read_bytes()
    assert json.loads(before) == json.loads(after), (
        "the backtest run from the dashboard did not reproduce the "
        "committed evaluation report"
    )

# ------------------------------------------------------------- the charts
def test_every_chart_actually_plots_something():
    """A chart with no data renders as an empty grid, and nobody notices.

    That is not hypothetical: the dial chart used to be exactly that. The
    dial is a *monthly* series, so on the daily equity axis it was NaN
    almost everywhere, the line broke into fragments, and the chart came
    out blank -- while the code looked fine and the test suite was green.

    So every figure is built here and checked for actual plotted points.
    """
    from dashboard import charts, data

    frame = data.load_equity()
    if frame is None:
        pytest.skip("no reports/equity.csv")

    payload = data.load_report() or {}
    vetoes = payload.get("vetoes") or []
    trades = payload.get("trades") or []
    walkforward = payload.get("walkforward") or []
    summary = payload.get("summary", {})

    figures = {
        "equity": charts.equity_figure(frame, walkforward),
        "drawdown": charts.drawdown_figure(frame),
        "dial": charts.dial_figure(frame),
        "veto_figure": charts.veto_figure(vetoes),
        "veto_stage": charts.veto_stage_figure(vetoes),
        "cost": charts.cost_figure(trades),
        "walkforward": charts.walkforward_figure(walkforward),
        "r2": charts.r2_figure(summary.get("r_squared", 0.0), 0.25),
    }

    for name, figure in figures.items():
        assert figure.data, f"the {name} chart has no traces at all"
        plotted = 0
        for trace in figure.data:
            y = getattr(trace, "y", None)
            if y is not None:
                plotted += sum(1 for v in y if v is not None)
            elif getattr(trace, "value", None) is not None:
                # A gauge (go.Indicator) renders a number, not points.
                plotted += 1
        assert plotted > 0, (
            f"the {name} chart has {len(figure.data)} trace(s) but plotted "
            "no points -- it would render as an empty grid"
        )


def test_the_dial_chart_uses_the_decision_days():
    """The dial is monthly. It must be plotted on its own dates."""
    from dashboard import charts, data

    frame = data.load_equity()
    if frame is None:
        pytest.skip("no reports/equity.csv")
    figure = charts.dial_figure(frame)
    observed = frame.dropna(subset=["dial"])
    if observed.empty:
        pytest.skip("the desk took no decisions in this run")
    plotted = [tr for tr in figure.data if tr.name == "dial"]
    assert plotted, "the dial chart has no dial trace"
    assert len(plotted[0].y) == len(observed), (
        "the dial chart must plot exactly the days the desk decided"
    )
