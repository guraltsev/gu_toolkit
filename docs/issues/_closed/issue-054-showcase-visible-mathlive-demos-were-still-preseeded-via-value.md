# Issue 054: The showcase notebook still pre-seeded visible MathLive demo widgets with `value=`, masking the real browser-driven workflow

## Status
Closed (2026-04-04)

## Summary
`examples/MathLive_identifier_system_showcase.ipynb` was still constructing the visible `IdentifierInput` and `ExpressionInput` demo widgets with `value=...` in their constructors.

That contradicted the notebook's intended teaching model. The visible sections were supposed to demonstrate real browser-driven interaction, but constructor-seeding let the notebook execute in a kernel-only run without proving that the frontend widget was actually rendering or syncing edits correctly. It also violated the explicit review request to stop presetting the visible demos that way and to use browser-side injection for the interactive walkthrough.

## Evidence
- The notebook previously created visible demo widgets with constructor presets such as:
  - `IdentifierInput(context=ctx, value=r"a_{1,2}")`
  - `ExpressionInput(context=ctx, value=r"\operatorname{Force}(\mathrm{theta\_x}) + 2\mathrm{velocity}")`
- The expression walkthrough had no matching browser-side injection cell, so the visible demo still depended on kernel-side seeding instead of live frontend interaction.
- The original notebook bug comments explicitly called this out: the visible walkthrough was supposed to use a fresh widget and browser-side JavaScript injection rather than fake the behavior via kernel-side `value` mutation.
- The updated notebook now:
  - starts both visible demo widgets empty,
  - adds optional browser-side injection cells for **both** identifier and expression demos,
  - keeps feedback/inspection cells tolerant of headless kernel-only execution, and
  - uses fresh widgets for later kernel-side regression checks.
- Structural regression coverage now lives in `tests/semantic_math/test_showcase_notebooks.py`, which checks that the visible demo cells do not use constructor `value=` seeding and that both demo sections retain their JavaScript injection path.

## TODO / Approach to solution
- [x] Remove `value=` constructor presets from the visible notebook demo widgets.
- [x] Keep the visible walkthrough honest by providing explicit browser-side injection cells.
- [x] Make the feedback/inspection cells safe in headless notebook execution when no frontend has populated the visible widget yet.
- [x] Keep backend regression coverage, but move it to fresh kernel-side widgets instead of the visible teaching widgets.
- [x] Add notebook-structure tests that protect the new visible-demo contract.

## Exit criteria
- [x] The visible identifier and expression demo widgets start empty.
- [x] The notebook contains optional browser-side injection cells for both visible demos.
- [x] Kernel-only notebook execution no longer depends on constructor-seeded visible widget state.
- [x] Structural tests protect the no-`value=` visible-demo contract and the presence of the injection cells.
