# Math input guide

This guide documents the **Phase 2** audited MathLive rebuild surface.

The rebuild still keeps the generic field small and explicit, but Phase 2 adds
one separate specialized widget for identifiers so the user can visibly compare
it with a generic expression field.

## Public API

Start here:

```python
from gu_toolkit import MathInput, IdentifierInput
```

The public surface in this phase is:

- `MathInput(value="")`
- `IdentifierInput(value="", context_names=(), context_policy="context_only")`

## `MathInput`: generic expression baseline

`MathInput` is still the generic baseline.

Its public contract remains intentionally small:

- `field.value` is always a Python `str`
- the string is treated as raw LaTeX
- Python constructor input initializes the frontend field
- frontend edits flow back to Python through the same `value` trait
- Python assignment to `field.value` overwrites the rendered field

`MathInput` does **not** do identifier policies, context suggestions, or menu
restriction. It remains the comparison point for the notebook.

## `IdentifierInput`: separate plain-identifier field

`IdentifierInput` is a **separate class**, not a role flag on `MathInput`.

Its public contract in Phase 2 is intentionally narrower than the generic
field:

- `field.value` is a plain identifier string, not raw LaTeX
- the empty string is allowed
- any non-empty value must match `[A-Za-z][A-Za-z0-9]*`
- `context_names` must use that exact same representation
- `context_policy` is explicit and must be one of:
  - `"context_only"`
  - `"context_or_new"`

### Context policies

`context_only`
: Only names listed in `context_names` are accepted.

`context_or_new`
: Names listed in `context_names` are suggested through the identifier field
  menu, but a new plain identifier is also accepted if it matches the
  published contract.

The policy is **not inferred** from whether `context_names` is empty or not.
Set it explicitly in notebook-facing code even though the Python constructor
still keeps a published default.

### Accepted value versus visible draft

When the identifier field contains accepted content, the visible field and the
Python `value` trait match.

When the user types invalid content, the widget is intentionally more explicit:

- the invalid draft may remain visible in the field,
- the field should show invalid visual feedback,
- the synchronized Python `value` trait keeps the **last accepted** identifier.

This makes failure visible instead of silently clearing the field, while still
keeping Python state constrained to the published contract.

On rerender or other Python-driven updates, the frontend resets to the last
accepted synchronized value.

## What Phase 2 visibly adds for identifiers

Compared with `MathInput`, the identifier field is intentionally more
constrained:

- it exposes explicit context-name suggestions in the identifier field menu
- it keeps the visible widget surface to the MathLive field itself
- it uses an explicit context admission policy
- it keeps only basic editing commands in the identifier menu
- it removes identifier-irrelevant menu categories such as solve/evaluate,
  styling/background, and broad expression-insertion helpers
- it disables inline shortcut conversion for identifiers so names such as `sin`
  or `log` stay plain text instead of turning into built-in function input
- it hides the virtual-keyboard toggle for this specialized field

The notebook is the main place to verify those differences manually.

## What Phase 2 intentionally leaves out

The identifier field is **not** a general semantic naming engine yet.

This phase deliberately does **not** implement:

- broader `gu_toolkit.identifiers` canonical semantics
- underscores in canonical identifier values
- subscripts or superscripts as canonical identifier structure
- Greek-name policies
- raw LaTeX identifier values such as `\mathrm{...}`
- automatic semantic interpretation of names
- broad symbolic intelligence
- mutation of a generic field into an identifier role

If those behaviors are needed later, they should arrive in separate phases with
separate visible notebook checks.

## Runtime notes

Both widget classes now configure explicit MathLive asset paths before their
fields are created.

The current frontend bridge:

- points MathLive font loading at an explicit versioned CDN font directory, and
- disables MathLive sound asset loading so the notebook does not request the
  missing default `plonk.wav` path.

For `IdentifierInput`, option and shortcut restrictions are applied as
post-mount MathfieldElement property assignments, and the constrained menu is
attached only after the mathfield mounts.

## Canonical verification notebook

Use this notebook as the primary evidence surface for the phase:

- `examples/MathLive_identifier_system_showcase.ipynb`

The filename is legacy. It remains the stable canonical notebook path so the
verification surface is easy to find and is not hidden behind a renamed file.

## Suggested verification flow

1. Open the canonical notebook.
2. Run the setup/import cell.
3. Compare the generic expression field with the identifier fields.
4. Open each visible menu and confirm the identifier field is more constrained.
5. Check the provided context names printed in the notebook.
6. Test one `context_only` field with an allowed name and an unknown name.
7. Confirm that an invalid `context_only` name stays visible with invalid
   styling while the backend value cell still shows the last accepted name.
8. Test one `context_or_new` field with a suggested name, a new plain name,
   and expression-like input such as `x+1`, `sin(x)`, `x_1`, or `\alpha`.
9. Try typing `sin` or `log` as plain text and confirm the field does **not**
   convert them into built-in MathLive function commands.
10. Optionally inspect the browser console while running the notebook and watch
    for MathLive startup errors.

## Read next

- `docs/guides/api-discovery.md`
- `examples/MathLive_identifier_system_showcase.ipynb`
- `tests/test_math_input_widget.py`
- `tests/test_identifier_input_widget.py`
