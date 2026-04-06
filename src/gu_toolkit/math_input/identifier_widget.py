"""Minimal audited identifier-input widget for the MathLive rebuild.

Phase 2 adds one specialized widget on top of the generic ``MathInput``
baseline: ``IdentifierInput``. The specialization is intentionally narrow and
explicit.

The public contract in this phase is:

- ``value`` is a plain identifier string, not raw LaTeX.
- Allowed non-empty values match ``[A-Za-z][A-Za-z0-9]*``.
- ``context_names`` uses the exact same representation as ``value``.
- ``context_policy`` is explicit and never inferred from the presence or
  absence of context names.
- The Python ``value`` trait changes only when the frontend content is
  accepted under the published rule.
- Invalid frontend drafts may remain visible for correction, but they do not
  overwrite the last accepted Python value.

This widget deliberately does **not** reuse the broader identifier semantics in
``gu_toolkit.identifiers``. The goal here is a visibly constrained notebook
field, not a general symbolic naming system.

Examples
--------
Create an identifier field that only accepts names from a provided context::

    from gu_toolkit import IdentifierInput
    field = IdentifierInput(
        value="mass",
        context_names=["mass", "time", "speed"],
        context_policy="context_only",
    )
    field

Create an identifier field that suggests context names through its menu but
also allows a new plain identifier::

    field = IdentifierInput(
        context_names=["mass", "time", "speed"],
        context_policy="context_or_new",
    )

Learn more / explore
--------------------
- Start with ``docs/guides/api-discovery.md`` for a task-oriented map of the package.
- Guide: ``docs/guides/math-input.md``.
- Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
- Contract tests: ``tests/test_math_input_widget.py`` and ``tests/test_identifier_input_widget.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import traitlets
from traitlets import TraitError

from .widget import MathInput

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_CONTEXT_POLICIES = ("context_only", "context_or_new")
MODULE_DIR = Path(__file__).resolve().parent
IDENTIFIER_INPUT_ESM_PATH = MODULE_DIR / "_identifier_input_widget.js"
IDENTIFIER_INPUT_CSS_PATH = MODULE_DIR / "_identifier_input_widget.css"


def _normalize_context_names(value: Iterable[str]) -> list[str]:
    names = list(value)
    seen: set[str] = set()
    for name in names:
        _validate_identifier_value(name, field_name="context_names entry")
        if name in seen:
            raise TraitError(
                f"context_names must not contain duplicates; repeated entry {name!r} found."
            )
        seen.add(name)
    return names



def _validate_identifier_value(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TraitError(f"{field_name} must be a string.")
    if value == "":
        return value
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise TraitError(
            f"{field_name} must be empty or match [A-Za-z][A-Za-z0-9]*; got {value!r}."
        )
    return value



def _validate_value_against_policy(
    value: str,
    *,
    context_names: list[str],
    context_policy: str,
    field_name: str,
) -> str:
    _validate_identifier_value(value, field_name=field_name)
    if value == "":
        return value
    if context_policy == "context_only" and value not in context_names:
        raise TraitError(
            f"{field_name} {value!r} is not present in context_names under context_only policy."
        )
    return value


class IdentifierInput(MathInput):
    """Render a visibly constrained notebook identifier field with explicit context policy.

    Full API
    --------
    ``IdentifierInput(value: str = "", context_names: Iterable[str] = (), context_policy: str = "context_only", **kwargs: Any)``

    Public members exposed from this class: ``value``, ``context_names``, ``context_policy``

    Parameters
    ----------
    value : str, optional
        Plain identifier string synchronized between Python and the frontend
        when the current frontend content is accepted. The empty string is
        allowed. Any non-empty value must match ``[A-Za-z][A-Za-z0-9]*``.
        Defaults to ``""``.

    context_names : Iterable[str], optional
        Allowed or menu-suggested identifier names, depending on ``context_policy``.
        Every entry must use the same plain-string identifier representation as
        ``value``. Defaults to ``()``.

    context_policy : str, optional
        Explicit identifier policy. Use ``"context_only"`` to accept only
        names listed in ``context_names``. Use ``"context_or_new"`` to suggest
        names from ``context_names`` through the identifier menu while still
        allowing a new plain
        identifier that matches the published contract. Defaults to
        ``"context_only"``.

    **kwargs : Any, optional
        Additional widget keyword arguments forwarded to the underlying widget
        base class, such as ``layout``. Optional variadic input.

    Returns
    -------
    IdentifierInput
        Widget instance whose ``value``, ``context_names``, and
        ``context_policy`` traits are synchronized with the rendered identifier
        field.

    Optional arguments
    ------------------
    - ``value=""``: Plain identifier string mirrored between Python and the frontend when accepted.
    - ``context_names=()``: Context identifiers exposed through the identifier menu.
    - ``context_policy="context_only"``: Explicit identifier admission policy.
    - ``**kwargs``: Forwarded widget keywords. When omitted, the widget uses a
      simple full-width layout.

    Architecture note
    -----------------
    ``IdentifierInput`` is a separate subclass rather than a role flag layered
    onto ``MathInput``. It reuses the generic MathLive bridge only as a basic
    editable field and then adds a very small, explicit Phase 2 contract:
    plain-name validation, explicit context policy, menu-based context
    suggestions, and a more restricted menu surface. Invalid frontend drafts
    may remain visible so
    the user can correct them manually, but only accepted values propagate back
    to the synchronized Python ``value`` trait. It intentionally does **not**
    adopt the broader identifier semantics from ``gu_toolkit.identifiers``.

    Examples
    --------
    Context-only identifier field::

        from gu_toolkit import IdentifierInput
        field = IdentifierInput(
            value="mass",
            context_names=["mass", "time", "speed"],
            context_policy="context_only",
        )
        field

    Suggest-or-new identifier field::

        field = IdentifierInput(
            context_names=["mass", "time", "speed"],
            context_policy="context_or_new",
        )
        field.value = "angle"

    Learn more / explore
    --------------------
    - Start with ``docs/guides/api-discovery.md`` for a task-oriented map.
    - Guide: ``docs/guides/math-input.md``.
    - Canonical rebuild notebook: ``examples/MathLive_identifier_system_showcase.ipynb``.
    - Contract tests: ``tests/test_math_input_widget.py`` and ``tests/test_identifier_input_widget.py``.
    """

    # Keep asset source paths explicit and module-local.
    # Real anywidget may replace MathInput._esm/_css with wrapped asset objects
    # during class creation, so deriving identifier assets from those runtime
    # attributes is not import-safe.
    _esm = IDENTIFIER_INPUT_ESM_PATH
    _css = IDENTIFIER_INPUT_CSS_PATH

    context_names = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(sync=True)
    context_policy = traitlets.Enum(_CONTEXT_POLICIES, default_value="context_only").tag(sync=True)

    def __init__(
        self,
        value: str = "",
        context_names: Iterable[str] = (),
        context_policy: str = "context_only",
        **kwargs: Any,
    ) -> None:
        normalized_context_names = _normalize_context_names(context_names)
        if context_policy not in _CONTEXT_POLICIES:
            raise TraitError(
                "context_policy must be one of "
                f"{_CONTEXT_POLICIES!r}; got {context_policy!r}."
            )
        _validate_value_against_policy(
            value,
            context_names=normalized_context_names,
            context_policy=context_policy,
            field_name="value",
        )

        super().__init__(value="", **kwargs)
        self.context_names = normalized_context_names
        self.context_policy = context_policy
        if value != "":
            self.value = value

    @traitlets.validate("value")
    def _validate_value_trait(self, proposal: dict[str, Any]) -> str:
        value = proposal["value"]
        return _validate_value_against_policy(
            value,
            context_names=list(self.context_names),
            context_policy=str(self.context_policy),
            field_name="value",
        )

    @traitlets.validate("context_names")
    def _validate_context_names_trait(self, proposal: dict[str, Any]) -> list[str]:
        normalized = _normalize_context_names(proposal["value"])
        _validate_value_against_policy(
            str(self.value),
            context_names=normalized,
            context_policy=str(self.context_policy),
            field_name="value",
        )
        return normalized

    @traitlets.validate("context_policy")
    def _validate_context_policy_trait(self, proposal: dict[str, Any]) -> str:
        policy = proposal["value"]
        if policy not in _CONTEXT_POLICIES:
            raise TraitError(
                "context_policy must be one of "
                f"{_CONTEXT_POLICIES!r}; got {policy!r}."
            )
        _validate_value_against_policy(
            str(self.value),
            context_names=list(self.context_names),
            context_policy=str(policy),
            field_name="value",
        )
        return str(policy)
