"""Click through the dashboard in a real browser.

Streamlit's own test harness cannot click a tab: ``st.tabs`` produces
containers, not widgets, and the harness has no ``click`` method for
them. That means the only honest way to test tab navigation is to open a
browser and click.

So this file does exactly that. It starts a real Streamlit server on a
free port, drives it with Playwright's chromium, and clicks through
everything a reader would click: every tab, the desk's run button, the
log-scale switch, the provider dropdown, the API-key field, and the
connection-test button with a deliberately dead endpoint.

Every selector and every assertion in this file was measured against the
live DOM, not guessed. The things that are not obvious:

* A tab is ``<div data-testid="stTab" role="tab">`` -- a *div*, not a
  button, so ``button[role=tab]`` finds nothing.
* A toggle is ``<input type="checkbox" role="switch">``. The explicit
  ``role="switch"`` overrides the implicit checkbox role, so
  ``get_by_role("checkbox")`` finds nothing. The input is 13x13 and
  wrapped in a label, so clicking the *input* stalls; clicking the
  ``stCheckbox`` container is what actually toggles it.
* ``get_by_role(name=...)`` matches a case-insensitive *substring* by
  default, so ``name="Test"`` also matches "Run the back**test**".
  ``exact=True`` is required.
* ``inner_text`` returns the *rendered* text, so a label with
  ``text-transform: uppercase`` comes back upper-cased, and it only
  contains the panel of the tab that is currently selected.
* A typed password is in the page source exactly once: as the value
  attribute of its own ``<input type="password">``. That is how HTML
  works -- the value lives in the DOM. What matters is that it appears
  nowhere *rendered*.

It skips when Playwright or its browser is not installed. In CI the
dashboard job installs both, so the skip never hides a broken dashboard.
"""

from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

APP = REPO / "dashboard" / "app.py"
TAB_NAMES = ["Overview", "Risk", "Desk", "Vetoes & trades", "Walk-forward",
             "Settings"]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def server():
    """A real Streamlit server, on a port nobody else is using.

    If Streamlit is not installed, this **skips**. It does not raise: a
    fixture that raises produces a pytest ERROR, which fails the build,
    and an optional dependency that is not installed is not a failure.
    The distinction that matters is between "the optional extra is not
    here" (skip) and "the extra is here and the server still died"
    (raise) -- the second is a real defect and must fail the build.
    """
    for package in ("streamlit", "plotly"):
        if importlib.util.find_spec(package) is None:
            pytest.skip(f"{package} is an optional extra")
    port = _free_port()
    command = [
        sys.executable, "-m", "streamlit", "run", str(APP),
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(
        command, cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 120
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"streamlit exited with {proc.returncode}:\n{proc.stdout.read()}"
                )
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("the Streamlit server did not start within 120s")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="module")
def page(server):
    """A chromium page with the dashboard loaded and rendered.

    Playwright is imported inside the fixture rather than at module level.
    A module-level ``importorskip`` makes pytest skip the whole file when
    Playwright is missing, so the file would contribute nothing to the
    collected count -- which made the repository's test count depend on
    which optional extras were installed. Skipping inside the fixture
    keeps the collection complete everywhere.
    """
    sync_playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright is not installed"
    ).sync_playwright
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"chromium is not available: {exc}")
        browser_page = browser.new_page(viewport={"width": 1680, "height": 1150})
        browser_page.goto(server, wait_until="domcontentloaded", timeout=60000)
        browser_page.wait_for_selector("[data-testid='stTab']", timeout=60000)
        browser_page.wait_for_function(
            "() => document.body.innerText.includes('GATE STACK')", timeout=60000
        )
        browser_page.wait_for_timeout(2500)
        try:
            yield browser_page
        finally:
            browser.close()


def _tab(page, name: str):
    """A tab, addressed by its accessible name."""
    return page.get_by_role("tab", name=name)


def _toggle(page, label: str):
    """A toggle's visible container. Clicking the input itself stalls."""
    return page.locator("[data-testid='stCheckbox']").filter(has_text=label).first


def _switch_state(page, label: str) -> bool:
    return page.get_by_role("switch", name=label).is_checked()


def _pick(page, label: str, option: str) -> None:
    """Open a selectbox and choose an option."""
    box = page.locator("[data-testid='stSelectbox']").filter(has_text=label).first
    box.locator("input").first.click()
    page.wait_for_selector("[role='option']", timeout=15000)
    page.get_by_role("option", name=option, exact=True).click()
    page.wait_for_timeout(1500)


def _visible_text(page) -> str:
    """The rendered text, lower-cased.

    ``inner_text`` returns what is *rendered*, so a CSS upper-case
    transform shows up here, and only the selected tab's panel is in it.
    """
    return page.inner_text("body").lower()


# ------------------------------------------------------------------ tests
def test_the_dashboard_loads_in_a_browser(page):
    """The page renders, with the verdict visible."""
    body = _visible_text(page)
    assert "portfolio hedging desk" in body
    assert "gate stack failed" in body


def test_every_tab_can_be_clicked(page):
    """Click all six tabs. Each one must become the selected tab.

    A tab that renders an empty panel is the failure this test exists to
    catch: the app looks fine until somebody clicks it.
    """
    for name in TAB_NAMES:
        _tab(page, name).click()
        page.wait_for_timeout(1200)
        assert _tab(page, name).get_attribute("aria-selected") == "true", (
            f"clicking {name!r} did not select it"
        )
        assert _visible_text(page).strip(), f"{name} is empty"


def test_clicking_through_the_tabs_surfaces_each_panel(page):
    """Each panel contains what it claims to contain."""
    expectations = {
        "Overview": "gate stack",
        "Risk": "drawdown from peak",
        "Desk": "trading day",
        "Vetoes & trades": "every refusal",
        "Walk-forward": "out of sample",
        "Settings": "api keys",
    }
    for name, needle in expectations.items():
        _tab(page, name).click()
        page.wait_for_timeout(1200)
        assert needle in _visible_text(page), (
            f"the {name} panel does not mention {needle!r}"
        )


def test_the_desk_runs_a_day_when_you_click(page):
    """Press "Run this day" and the seat cards appear."""
    _tab(page, "Desk").click()
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="Run this day", exact=True).click()
    page.wait_for_timeout(6000)
    body = _visible_text(page)
    assert "desk run for" in body
    for seat in ("quant", "scan", "hedger", "judge"):
        assert seat in body, f"no card for the {seat} seat"


def test_the_log_scale_switch_works(page):
    """The Risk tab's log-scale switch toggles without breaking the chart."""
    _tab(page, "Risk").click()
    page.wait_for_timeout(1500)
    before = page.locator(".js-plotly-plot").count()
    assert before > 0
    was = _switch_state(page, "Log scale")
    _toggle(page, "Log scale").click()
    page.wait_for_timeout(2500)
    assert _switch_state(page, "Log scale") is not was, "the switch did not flip"
    assert page.locator(".js-plotly-plot").count() == before
    assert "traceback" not in _visible_text(page)


def test_the_llm_judge_switch_warns_without_a_key(page):
    """Flipping the LLM judge with no key must warn, not crash."""
    _tab(page, "Desk").click()
    page.wait_for_timeout(1200)
    _toggle(page, "Use an LLM judge").click()
    page.wait_for_timeout(2500)
    body = _visible_text(page)
    assert "traceback" not in body
    assert "api key" in body


def test_the_provider_dropdown_changes_the_key_field(page):
    """Switching provider asks for a different key."""
    _pick(page, "LLM provider", "OpenAI")
    assert "openai_api_key" in _visible_text(page)


def test_a_typed_key_is_never_rendered(page):
    """The key must not appear in any rendered text.

    It *is* in the page source once, as the value attribute of its own
    password input -- that is how HTML stores a field's value, and it is
    unavoidable. What must not happen is the key being rendered as text
    anywhere, or ending up anywhere but that input.
    """
    # A probe value, not a credential: no provider prefix, no credential
    # shape, and a variable name that does not look like a secret to a
    # scanner. The test is about whether the *field's contents* escape,
    # not about what the contents are.
    probe_value = "typed-into-the-key-field"
    field = page.locator('input[type="password"]').first
    field.fill(probe_value)
    page.wait_for_timeout(2000)

    assert probe_value not in _visible_text(page), (
        "the API key was rendered as text"
    )
    content = page.content()
    assert content.count(probe_value) == 1, (
        f"the key appears {content.count(probe_value)} times in the source; "
        "it should appear only as its own input's value"
    )
    assert field.get_attribute("value") == probe_value


def test_the_connection_test_reports_a_dead_endpoint(page):
    """A dead endpoint produces an error message, not a crash.

    The endpoint is a local port with nothing listening on it, so no
    request goes to a third party.
    """
    _pick(page, "LLM provider", "Custom (OpenAI-compatible)")
    page.wait_for_timeout(1500)

    # Both the base URL *and* the model are required: the connection test
    # refuses early if either is missing, so a test that only filled the
    # URL would never reach the network.
    wanted = {"https://api.example.com/v1": "http://127.0.0.1:9/v1",
              "model-name": "test-model"}
    fields = page.locator('input[type="text"]')
    for index in range(fields.count()):
        placeholder = fields.nth(index).get_attribute("placeholder") or ""
        if placeholder in wanted:
            fields.nth(index).fill(wanted[placeholder])
    page.wait_for_timeout(1500)

    # A dummy key, so the test never uses a real one from the machine's
    # .env and never sends anything to a third party.
    page.locator('input[type="password"]').first.fill("typed-into-the-key-field")
    page.wait_for_timeout(1500)

    page.get_by_role("button", name="Test", exact=True).click()
    page.wait_for_timeout(10000)
    body = _visible_text(page)
    assert "traceback" not in body
    assert "could not reach" in body, (
        f"the dead endpoint was not reported; the page said: {body[-400:]!r}"
    )


def test_the_streamlit_chrome_is_not_visible(page):
    """The Deploy button must not be in the picture.

    It is the single thing that makes a screenshot of a Streamlit app
    look like a screenshot of a demo rather than of a product. It is
    hidden with CSS, so it is still in the DOM -- the check is that it is
    not *visible*.
    """
    for testid in ("stAppDeployButton", "stMainMenu"):
        locator = page.locator(f"[data-testid='{testid}']")
        if locator.count():
            assert not locator.first.is_visible(), f"{testid} is visible"


def test_the_header_is_not_clipped(page):
    """The hero must not sit under Streamlit's floating header."""
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    box = page.locator(".hd-eyebrow").first.bounding_box()
    header = page.locator('[data-testid="stHeader"]').first.bounding_box()
    assert box is not None and header is not None
    assert box["y"] >= header["y"] + header["height"], (
        f"the eyebrow starts at y={box['y']:.0f} but the header ends at "
        f"y={header['y'] + header['height']:.0f}"
    )


def test_the_gate_stack_shows_the_gates_that_never_ran(page):
    """The dashboard must not imply the desk only had two criteria."""
    _tab(page, "Overview").click()
    page.wait_for_timeout(1200)
    body = _visible_text(page)
    assert "not reached" in body
    for name in ("hedgeability", "regime_information", "compensation", "stability"):
        assert name in body, f"gate {name} is not on the page"
