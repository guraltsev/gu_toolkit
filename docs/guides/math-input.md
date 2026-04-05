# Math input guide

This guide documents the **Phase 1** math-input rebuild surface.

The goal of this phase is intentionally narrow: provide one small, auditable
widget that renders a math field in a notebook and keeps a single raw-string
value synchronized between the frontend and Python.

## Public API

Start here:

```python
from gu_toolkit import MathInput
```

The public contract is one class and one synchronized trait:

- `MathInput(value="")`
- `field.value` → raw LaTeX string

That is the whole Phase 1 surface.

## What Phase 1 does

- initializes a field from Python using `value`
- renders a notebook widget
- sends user edits back to Python through the same `value` trait
- allows Python to overwrite the current value by assigning `field.value = ...`
- keeps new widget instances independent of older ones

## What Phase 1 does **not** do

The rebuild deliberately leaves these out for now:

- identifier-specific restrictions
- context-aware suggestions
- unknown-name policies
- role switching between expression and identifier modes
- custom menu logic
- semantic parsing or validation of the entered math

If you need any of those behaviors, they belong in later rebuild phases with
separate visible notebook checks.

## Serialization and value contract

`field.value` is always a Python `str`.

It is treated as the raw LaTeX payload owned by the widget model:

- Python constructor input → frontend math field
- frontend user edits → Python `field.value`
- Python assignment to `field.value` → frontend math field

Phase 1 intentionally does **not** interpret this string semantically. The
widget is a transport bridge, not a parser or policy engine.

## Runtime notes

The notebook-facing widget uses an AnyWidget frontend module and loads MathLive
inside that frontend bridge. The Python API does not expose MathLive classes or
MathLive-specific policies.

In environments without real widget support, you may see a plain object repr
instead of a rendered field. That blocks manual UI verification and should be
resolved before evaluating the notebook behavior.

## Canonical verification notebook

Use this notebook as the primary evidence surface for the phase:

- `examples/MathLive_identifier_system_showcase.ipynb`

The filename is legacy. It is kept in place so the rebuild keeps one stable,
visible notebook path instead of hiding the old evidence surface behind a new
name.

## Suggested verification flow

1. Open the canonical notebook.
2. Run the setup/import cell.
3. Confirm the initial field renders from Python.
4. Manually edit the field.
5. Run the next cell that reads `field.value`.
6. Assign a new value from Python and watch the field update.
7. Create a new widget instance and confirm it starts from its own constructor
   value.

## Read next

- `docs/guides/api-discovery.md`
- `examples/MathLive_identifier_system_showcase.ipynb`
- `tests/test_math_input_widget.py`
