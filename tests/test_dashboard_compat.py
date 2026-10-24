"""The Streamlit width shim must work on the installed version AND on the
versions a reader might have.

Two things are proved here:

1. On the INSTALLED Streamlit, the shim returns keyword arguments the
   widget actually accepts. A shim that returns `width="stretch"` on a
   version that only takes an int is broken, and it is broken in a way
   that raises TypeError at render time.

2. The FALLBACK works. The fallback is the branch a reader on an old
   Streamlit hits, so it is the branch that matters most -- and a test
   that only exercises the installed version never touches it. The
   fallback is proved by asking the shim about a widget that does NOT
   accept "stretch", which is exactly the old-Streamlit situation.

**The Streamlit import is lazy, on purpose.** Streamlit is an optional
extra. The first draft of this file imported it at module level, which
made pytest ERROR at collection on a base install -- and an ERROR fails
the build where a SKIP does not. A module-level ``importorskip`` is the
wrong fix: it makes the whole file disappear from the collected count, so
"how many tests does this repository have" would depend on which extras
are installed -- the exact defect this repository already fixed once (see
the ``app_test`` fixture in tests/test_dashboard.py). So the import
happens inside a fixture, and the collected count stays a property of the
repository.
"""

from __future__ import annotations

import importlib.util
import inspect
import typing
from pathlib import Path

import pytest

# The dashboard needs both of these, and neither is in the core install.
DASHBOARD_EXTRA = ("streamlit", "plotly")


@pytest.fixture(scope="module")
def compat():
    """The shim module, imported lazily.

    Importing here rather than at module level keeps the collection
    complete in every environment, so the collected count does not depend
    on which optional extras are installed.
    """
    for package in DASHBOARD_EXTRA:
        if importlib.util.find_spec(package) is None:
            pytest.skip(f"{package} is an optional extra")

    from dashboard import compat as compat_module

    return compat_module


@pytest.fixture(scope="module")
def streamlit():
    """Streamlit itself, imported lazily, for the same reason."""
    for package in DASHBOARD_EXTRA:
        if importlib.util.find_spec(package) is None:
            pytest.skip(f"{package} is an optional extra")
    import streamlit as st

    return st


def test_installed_widgets_accept_what_the_shim_returns(compat, streamlit):
    """Every keyword the shim returns must be a real parameter of the
    widget, on the installed Streamlit."""
    for widget, kwargs in (
        (streamlit.button, compat.BUTTON_WIDTH),
        (streamlit.dataframe, compat.DATAFRAME_WIDTH),
        (streamlit.plotly_chart, compat.PLOTLY_WIDTH),
    ):
        params = inspect.signature(widget).parameters
        assert kwargs, "the shim must return something"
        for key in kwargs:
            assert key in params, (
                f"{widget.__name__} does not accept {key!r} on Streamlit "
                f"{streamlit.__version__}; the shim would raise TypeError at "
                f"render time"
            )


def test_shim_prefers_the_modern_spelling_when_it_is_accepted(compat, streamlit):
    """When the installed Streamlit accepts 'stretch', use it.

    The modern spelling is not deprecated; the old one is. Preferring the
    old spelling everywhere would produce a deprecation warning on every
    render for every reader on a current Streamlit.
    """
    if compat._accepts_stretch(streamlit.button):
        assert compat.BUTTON_WIDTH == {"width": "stretch"}
        assert compat.DATAFRAME_WIDTH == {"width": "stretch"}
        assert compat.PLOTLY_WIDTH == {"width": "stretch"}
    else:
        assert compat.BUTTON_WIDTH == {"use_container_width": True}


def test_fallback_is_used_when_stretch_is_not_accepted(compat, monkeypatch):
    """The fallback branch, proved.

    A widget whose `width` parameter does not accept the string must get
    the old spelling instead. This is the situation of every reader whose
    Streamlit predates the parameter, and it is the branch that a test
    running only on the newest Streamlit would never reach.
    """
    monkeypatch.setattr(compat, "_accepts_stretch", lambda widget: False)
    assert compat.width_kwargs(_FakeButton) == {"use_container_width": True}
    assert compat.width_kwargs(_FakeDataFrame) == {"use_container_width": True}
    assert compat.width_kwargs(_FakePlotly) == {"use_container_width": True}


def test_fallback_keyword_is_accepted_by_the_installed_widgets(compat, streamlit):
    """The fallback keyword must exist on the installed widgets too.

    `use_container_width` is available on every widget this app uses in
    every version measured from 1.40.0 to 1.61.1. If a future Streamlit
    removed it, the fallback would break silently -- so assert it.
    """
    for widget in (streamlit.button, streamlit.dataframe, streamlit.plotly_chart):
        params = inspect.signature(widget).parameters
        assert "use_container_width" in params, (
            f"{widget.__name__} no longer accepts use_container_width; the "
            f"fallback path would raise TypeError on Streamlit {streamlit.__version__}"
        )


def test_resolve_width_alias_reads_the_real_alias(compat, streamlit):
    """The alias must be resolved from the installed package, not guessed.

    The bug this guards against: a probe that string-matches a module's
    source and reports "does not accept 'stretch'" for every version,
    including versions that demonstrably do.
    """
    alias = compat._resolve_width_alias(streamlit.button)
    assert alias is not None, "could not resolve the Width alias"

    literals = set()
    for arg in typing.get_args(alias):
        if typing.get_origin(arg) is typing.Literal:
            literals |= set(typing.get_args(arg))
    assert literals, f"the Width alias carried no literal values: {alias!r}"


def test_describe_reports_the_resolution(compat, streamlit):
    report = compat.describe()
    assert report["streamlit"] == streamlit.__version__
    for key in ("button", "dataframe", "plotly_chart"):
        assert report[key], f"{key} resolved to no keyword arguments"


def test_no_hardcoded_width_in_the_dashboard():
    """The app must not hardcode `width="stretch"` anywhere.

    A hardcoded call site is a call site that raises TypeError on an older
    Streamlit, which is exactly the defect the shim exists to remove. The
    check reads the source, so it catches a call site the tests never
    render.

    This one needs no Streamlit: it reads a file. It runs on a base
    install, so the repository's collected count is the same everywhere.
    """
    app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    source = app.read_text(encoding="utf-8")
    assert 'width="stretch"' not in source, (
        "dashboard/app.py still hardcodes width=\"stretch\"; use the "
        "compat shim so an older Streamlit gets the app instead of a TypeError"
    )
    assert "use_container_width=True" not in source, (
        "dashboard/app.py hardcodes the deprecated spelling; use the shim"
    )


# ----------------------------------------------------------- fake widgets
# Stand-ins for the Streamlit widgets, used to drive the fallback branch
# without needing an old Streamlit installed.
class _FakeButton:
    def __call__(self, *a, **k):  # pragma: no cover - never called
        raise AssertionError("the shim must not call the widget")


class _FakeDataFrame:
    def __call__(self, *a, **k):  # pragma: no cover - never called
        raise AssertionError("the shim must not call the widget")


class _FakePlotly:
    def __call__(self, *a, **k):  # pragma: no cover - never called
        raise AssertionError("the shim must not call the widget")
