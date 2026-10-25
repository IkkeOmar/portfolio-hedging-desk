"""The dashboard's widget keys and application-state keys must be disjoint.

GOAL.md section 1d, item 26:

    "A widget key and an application-state key shared a string, and the
     widget silently overwrote the app's data. ... the two namespaces are
     disjoint, enforced by a test."

Streamlit stores a widget's value under its `key` in the same session
state the application uses for its own data. So a widget whose key equals
an application-state key does not merely collide in a dictionary -- the
widget's return value OVERWRITES the application's data, silently, and
the application reads back the widget's value instead of its own.

The current namespaces are disjoint: 12 widget keys, all prefixed `w_`,
and one application-state key, `app_desk_output`. This test is what
KEEPS them disjoint. Without it, the next key somebody adds can silently
break the desk's output, and nothing fails.

The test reads the source rather than importing the module, because
importing `dashboard.app` executes Streamlit code at import time, and
the point of this check is that it runs everywhere -- including where
Streamlit is not installed at all.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def _module_constants() -> dict[str, str]:
    """Every module-level string constant, by name."""
    tree = ast.parse(_source())
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    if isinstance(node.value.value, str):
                        out[target.id] = node.value.value
    return out


def _widget_keys() -> set[str]:
    """Every key a widget is created with.

    Resolves the K_* constants, so a key written as `key=K_CONFIG` is
    caught just as a literal is.
    """
    src = _source()
    consts = _module_constants()
    keys: set[str] = set()

    # literal: key="w_thing"
    keys |= set(re.findall(r'key\s*=\s*"([^"]+)"', src))

    # constant: key=K_SOMETHING  ->  resolve it
    for name in re.findall(r"key\s*=\s*(K_\w+)", src):
        if name in consts:
            keys.add(consts[name])

    # the two keys that are written inline in a call
    keys |= set(re.findall(r'"(w_custom_base_url|w_custom_model)"', src))

    return keys


def _state_keys() -> set[str]:
    """Every key the application stores its own data under."""
    src = _source()
    consts = _module_constants()
    keys: set[str] = set()

    # session_state[NAME] and session_state["name"]
    for name in re.findall(r"session_state\[\s*([A-Za-z_]\w*)\s*\]", src):
        keys.add(consts.get(name, name))
    for name in re.findall(r'session_state\[\s*"([^"]+)"\s*\]', src):
        keys.add(name)
    for name in re.findall(r"session_state\.([A-Za-z_]\w*)", src):
        keys.add(consts.get(name, name))

    return keys


def test_the_dashboard_has_both_namespaces():
    """A check that finds nothing because it looks in the wrong place is
    not a check. Both namespaces must be non-empty for the test below to
    mean anything."""
    assert _widget_keys(), "no widget keys found -- the check would be vacuous"
    assert _state_keys(), "no session_state keys found -- the check would be vacuous"


def test_widget_keys_and_state_keys_are_disjoint():
    """The overlap must be empty."""
    widgets = _widget_keys()
    state = _state_keys()
    overlap = widgets & state
    assert not overlap, (
        "these keys are used BOTH as a widget key and as an "
        f"application-state key: {sorted(overlap)}. A widget with such a key "
        "silently overwrites the application's data on every render."
    )


def test_widget_keys_are_prefixed():
    """The widget namespace is prefixed, so a collision is visible."""
    for key in _widget_keys():
        assert key.startswith("w_"), (
            f"widget key {key!r} is not prefixed with 'w_'. The application "
            "state key is 'app_desk_output'; a shared prefix convention is "
            "what keeps the two namespaces apart by eye as well as by test."
        )


def test_the_application_state_key_is_namespaced():
    """The application-state key is prefixed too."""
    for key in _state_keys():
        assert key.startswith("app_"), (
            f"application-state key {key!r} is not prefixed with 'app_'"
        )
