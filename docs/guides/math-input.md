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
: Names listed in `context_names` are suggested, but a new plain identifier is
  also accepted if it matches the published contract.

The policy is **not inferred** from whether `context_names` is empty or not.
Set it explicitly.

## What Phase 2 visibly adds for identifiers

Compared with `MathInput`, the identifier field is intentionally more
constrained:

- it offers explicit context-name suggestions
- it uses an explicit context admission policy
- it restricts the menu to basic editing commands only
- it removes identifier-irrelevant MathLive shortcut behavior such as broad
  Alt/Option insertion shortcuts and inline function shortcuts
- it hides the virtual-keyboard toggle for this specialized field

The notebook is the main place to verify those differences manually.

## What Phase 2 intentionally leaves out

The identifier field is **not** a general semantic naming engine yet.

This phase deliberately does **not** implement:

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

Both widget classes now go through one shared runtime bootstrap strategy for
MathLive loading and font configuration before their fields are created.

For `IdentifierInput`, mount-sensitive MathLive customization is applied only
after the `<math-field>` element has been attached, so Phase 2 does not rely on
pre-mount `inlineShortcuts` or menu mutation.

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
7. Test one `context_or_new` field with a suggested name, a new plain name, and
   expression-like input such as `x+1` or `sin(x)`.
8. Optionally inspect the browser console while running the notebook and watch
   for MathLive startup errors.

## Read next

- `docs/guides/api-discovery.md`
- `examples/MathLive_identifier_system_showcase.ipynb`
- `tests/test_math_input_widget.py`
- `tests/test_identifier_input_widget.py`
