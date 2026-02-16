from __future__ import annotations

import pytest
import sympy as sp

from gu_toolkit import Figure
from gu_toolkit.ParamEvent import ParamEvent


def test_parameter_returns_same_ref_stored_in_params() -> None:
    fig = Figure()
    a = sp.Symbol("a")

    ref = fig.parameter(a)

    assert ref is fig.params[a]
    assert ref.parameter == a


def test_parameter_defaults_on_first_creation() -> None:
    fig = Figure()
    a = sp.Symbol("a")

    ref = fig.parameter(a)

    assert ref.value == pytest.approx(0.0)
    if hasattr(ref, "min"):
        assert ref.min == pytest.approx(-1.0)
    if hasattr(ref, "max"):
        assert ref.max == pytest.approx(1.0)
    if hasattr(ref, "step"):
        assert ref.step == pytest.approx(0.01)


def test_existing_parameter_only_updates_explicit_fields() -> None:
    fig = Figure()
    a = sp.Symbol("a")

    fig.parameter(a, min=-4, max=4, step=0.25, value=1.5)
    updated = fig.parameter(a, value=2.25)

    assert updated.value == pytest.approx(2.25)
    if hasattr(updated, "min"):
        assert updated.min == pytest.approx(-4.0)
    if hasattr(updated, "max"):
        assert updated.max == pytest.approx(4.0)
    if hasattr(updated, "step"):
        assert updated.step == pytest.approx(0.25)


def test_setting_value_does_not_change_default_value() -> None:
    fig = Figure()
    a = sp.Symbol("a")

    ref = fig.parameter(a, value=0.1)

    if not hasattr(ref, "default_value"):
        pytest.skip("reference has no default_value capability")

    old_default = ref.default_value
    ref.value = 0.9
    assert ref.default_value == old_default


def test_paramref_observe_emits_paramevent() -> None:
    fig = Figure()
    a = sp.Symbol("a")
    ref = fig.parameter(a, value=0.0)

    events: list[ParamEvent] = []
    ref.observe(events.append, fire=True)

    ref.value = 1.0

    assert len(events) >= 2
    assert isinstance(events[-1], ParamEvent)
    assert events[-1].parameter == a
    assert events[-1].new == pytest.approx(1.0)
