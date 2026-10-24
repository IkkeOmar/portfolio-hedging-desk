"""Runtime compatibility for Streamlit's width parameters.

The dashboard wants its widgets to fill their container. Streamlit spells
that two different ways depending on the version, and getting it wrong is
not a warning -- it is a hard ``TypeError`` that stops the app:

* ``width="stretch"`` -- the modern spelling. It exists for
  ``st.button`` and ``st.dataframe`` from **1.49.0**, and for
  ``st.plotly_chart`` from **1.51.0**. The accepted values are the
  ``Literal["stretch", "content"]`` in
  ``streamlit.elements.lib.layout_utils.Width``.
* ``use_container_width=True`` -- the older spelling. Every widget this
  app uses accepts it, on every version measured from 1.40.0 to 1.61.1.
  It is deprecated on the newest versions and is scheduled for removal,
  so it is used ONLY as the fallback.

So the rule is: **prefer the modern spelling, fall back to the old one.**

Why feature-detect instead of version-gating:

* The reader's environment is not the repository's environment. A reader
  who has an older Streamlit already installed in the same interpreter
  gets the app, not a crash.
* A version gate (``if streamlit_version >= X``) is a second place to be
  wrong, and it goes stale the moment Streamlit renames or re-adds a
  parameter. Asking the installed package what it accepts cannot go
  stale.

The check resolves the ``Width`` alias the way the library defines it, by
looking the literal values up in ``typing.get_args``. It does **not**
string-match a module's source: a probe that reported "does not accept
'stretch'" for every version -- including one that demonstrably works --
is a broken probe, and it nearly cost this repository a floor version
that cannot render its own charts.
"""

from __future__ import annotations

import importlib
import inspect
import typing

import streamlit as st

__all__ = [
    "BUTTON_WIDTH",
    "DATAFRAME_WIDTH",
    "PLOTLY_WIDTH",
    "width_kwargs",
    "describe",
]


def _resolve_width_alias(widget) -> typing.Any | None:
    """The ``Width`` alias the widget's ``width`` parameter refers to.

    Resolved by looking the alias up, not by reading source text: the
    annotation on the widget is a forward reference to a type alias, and
    the alias lives in ``streamlit.elements.lib.layout_utils``.
    """
    try:
        params = inspect.signature(widget).parameters
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None
    if "width" not in params:
        return None

    annotation = params["width"].annotation

    # 1. The widget module's own namespace, when the annotation is a
    #    string forward reference.
    if isinstance(annotation, str):
        module = inspect.getmodule(widget)
        if module is not None:
            found = getattr(module, annotation, None)
            if found is not None:
                return found

    # 2. The module that defines the alias.
    for name in (
        "streamlit.elements.lib.layout_utils",
        "streamlit.elements.lib.utils",
        "streamlit.type_util",
    ):
        try:
            module = importlib.import_module(name)
        except Exception:  # pragma: no cover - defensive
            continue
        found = getattr(module, "Width", None)
        if found is not None:
            return found

    return None


def _accepts_stretch(widget) -> bool:
    """Does this widget's ``width`` parameter accept the string 'stretch'?"""
    alias = _resolve_width_alias(widget)
    if alias is None:
        return False
    for arg in typing.get_args(alias):
        if typing.get_origin(arg) is typing.Literal:
            if "stretch" in typing.get_args(arg):
                return True
    return False


def width_kwargs(widget) -> dict:
    """The keyword arguments that make ``widget`` fill its container.

    ``widget`` is the callable itself (``st.button``, ``st.dataframe``,
    ``st.plotly_chart``), so the decision is made per widget rather than
    per Streamlit version: the three widgets gained the modern parameter
    in three different releases.
    """
    if _accepts_stretch(widget):
        return {"width": "stretch"}
    # The old spelling. Available on every widget this app uses, in every
    # version measured from 1.40.0 upwards.
    return {"use_container_width": True}


# Resolved once at import: these are constants for the running process.
BUTTON_WIDTH = width_kwargs(st.button)
DATAFRAME_WIDTH = width_kwargs(st.dataframe)
PLOTLY_WIDTH = width_kwargs(st.plotly_chart)


def describe() -> dict:
    """What this process resolved to. Used by the test suite and the
    dashboard's own diagnostics."""
    return {
        "streamlit": st.__version__,
        "button": dict(BUTTON_WIDTH),
        "dataframe": dict(DATAFRAME_WIDTH),
        "plotly_chart": dict(PLOTLY_WIDTH),
    }
