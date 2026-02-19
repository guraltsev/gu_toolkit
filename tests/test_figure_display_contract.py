from __future__ import annotations

import sys
from unittest.mock import patch

from gu_toolkit import Figure
from gu_toolkit.figure_layout import OneShotOutput


def test_figure_constructor_is_display_side_effect_free() -> None:
    """Figure construction must not trigger IPython display calls."""
    module = sys.modules[Figure.__module__]
    with patch.object(module, "display") as mocked_display:
        fig = Figure()

    assert fig._has_been_displayed is False
    mocked_display.assert_not_called()


def test_ipython_display_marks_figure_as_displayed_once() -> None:
    """IPython display hook toggles lifecycle state and displays output widget."""
    fig = Figure()
    module = sys.modules[Figure.__module__]

    with patch.object(module, "display") as mocked_display:
        fig._ipython_display_()

    assert fig._has_been_displayed is True
    mocked_display.assert_called_once()
    assert isinstance(mocked_display.call_args.args[0], OneShotOutput)


def test_figure_constructor_display_true_forces_immediate_display() -> None:
    """Constructor display=True should trigger immediate rich display."""
    module = sys.modules[Figure.__module__]
    with patch.object(module, "display") as mocked_display:
        fig = Figure(display=True)

    assert fig._has_been_displayed is True
    mocked_display.assert_called_once()
    assert isinstance(mocked_display.call_args.args[0], OneShotOutput)
