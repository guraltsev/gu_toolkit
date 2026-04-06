# Math input guide

This guide documents the **Phase 3** audited MathLive rebuild surface.

The rebuild still keeps the generic field small and explicit, but Phase 3
extends `IdentifierInput` in one narrow direction: `context_or_new` now uses the
canonical identifier rules from `gu_toolkit.identifiers`, exposes a restricted
identifier-only virtual keyboard, allows Greek and subscripted identifiers, and
forbids function-like names through a configurable forbidden-symbol list.

## Public API

Start here:

```python
from gu_toolkit import MathInput, IdentifierInput
```

The public surface in this phase is:

- `MathInput(value="")`
- `IdentifierInput(value="", context_names=(), context_policy="context_only", forbidden_symbols=None)`

## `MathInput`: generic expression baseline

`MathInput` is still the generic baseline.

Its public contract remains intentionally small:

- `field.value` is always a Python `str`
- the string is treated as raw LaTeX
- Python constructor input initializes the frontend field
- frontend edits flow back to Python through the same `value` trait
- Python assignment to `field.value` overwrites the rendered field

`MathInput` does **not** do identifier policies, context suggestions, forbidden
identifier names, or keyboard restriction. It remains the comparison point for
notebook checks when a generic expression field is needed.

## `IdentifierInput`: separate canonical-identifier field

`IdentifierInput` is a **separate class**, not a role flag on `MathInput`.

Its public contract in Phase 3 is still narrower than the generic field:

- `field.value` is a canonical identifier string, not raw LaTeX
- the empty string is allowed
- any non-empty value must satisfy `gu_toolkit.identifiers.validate_identifier()`
- canonical examples include `mass`, `alpha`, `theta_x`, and `a_1_2`
- `context_names` must use that same canonical representation
- `context_policy` is explicit and must be one of:
  - `"context_only"`
  - `"context_or_new"`
- `forbidden_symbols` is explicit and defaults to common function-like names
  such as `sin`, `cos`, and `log`

### Context policies

`context_only`
: Only names listed in `context_names` are accepted.

`context_or_new`
: Names listed in `context_names` are suggested through the identifier field
  menu, but a new canonical identifier is also accepted if it satisfies the
  canonical identifier layer and is not forbidden.

The policy is **not inferred** from whether `context_names` is empty or not.
Set it explicitly in notebook-facing code even though the Python constructor
still keeps a published default.

### Forbidden symbols

`IdentifierInput` now bakes in a default forbidden-symbol list so common
function-like names do not become accepted identifier values by accident.

Important distinction:

- if a forbidden name is supplied from trusted Python-side configuration, such
  as `value` or `context_names`, construction or trait assignment raises,
- if a forbidden name is typed into the frontend, the field stays visibly
  invalid and the synchronized Python value keeps the last accepted identifier.

This keeps trusted state strict while leaving user drafts inspectable.

### Accepted value versus visible draft

When the identifier field contains accepted content, the visible field and the
Python `value` trait describe the same canonical identifier.

When the user types invalid or forbidden content, the widget is intentionally
more explicit:

- the invalid draft may remain visible in the field,
- the field should show invalid visual feedback,
- the synchronized Python `value` trait keeps the **last accepted** identifier.

This makes failure visible instead of silently clearing the field, while still
keeping Python state constrained to the published contract.

On rerender or other Python-driven updates, the frontend resets to the last
accepted synchronized value.

## What Phase 3 visibly adds for identifiers

Compared with `MathInput`, the identifier field is intentionally more
constrained:

- it exposes explicit context-name suggestions in the identifier field menu
- it keeps the visible widget surface to the MathLive field itself
- it uses an explicit context admission policy
- it keeps only basic editing commands plus a small identifier-specific insert
  action in the identifier menu
- it blocks forbidden function-like names through a baked-in configurable list
- it accepts canonical identifiers that map to Greek letters and subscripts
- it exposes a restricted virtual keyboard in `context_or_new`
- it allows subscript insertion through the menu and the keyboard
- it still disables inline shortcut conversion so plain typing does not turn the
  identifier field into a generic function-entry surface

The notebook is the main place to verify those differences manually.

## What Phase 3 intentionally leaves out

The identifier field is still **not** a general symbolic expression editor.

This phase deliberately does **not** implement:

- raw LaTeX assignment to the Python `value` trait
- broad expression editing inside `IdentifierInput`
- superscripted identifier values
- automatic acceptance of arbitrary MathLive structures
- broad symbolic intelligence
- mutation of a generic field into an identifier role

If those behaviors are needed later, they should arrive in separate phases with
separate visible notebook checks.

## Runtime notes

Both widget classes configure explicit MathLive asset paths before their fields
are created.

The current frontend bridge:

- points MathLive font loading at an explicit versioned CDN font directory,
- disables MathLive sound asset loading so the notebook does not request the
  missing default `plonk.wav` path,
- configures identifier restrictions only after the mathfield mounts,
- uses a restricted custom virtual keyboard for `context_or_new`, and
- limits script entry so subscripts are available while superscripts remain out
  of scope for identifier values.

## Canonical verification notebook

Use this notebook as the primary evidence surface for the phase:

- `examples/MathLive_identifier_system_showcase.ipynb`

The filename is legacy. It remains the stable canonical notebook path so the
verification surface is easy to find and is not hidden behind a renamed file.

## Suggested verification flow

1. Open the canonical notebook.
2. Run the setup/import cell.
3. Open the `IdentifierInput` menu and compare it with the printed context.
4. Open the keyboard toggle and inspect the visible layouts.
5. Select `theta_x` and `alpha` from the context submenu.
6. Use the keyboard or menu to insert a subscripted identifier such as `x_1`.
7. Type `sin` or `log` and confirm the field turns red while the Python value
   stays at the last accepted identifier.
8. Run the constructor-time forbidden-context check.
9. Run the custom-forbidden field demo and verify that the replacement forbidden
   list changes what is rejected.

## Read next

- `docs/guides/api-discovery.md`
- `examples/MathLive_identifier_system_showcase.ipynb`
- `tests/test_math_input_widget.py`
- `tests/test_identifier_input_widget.py`
