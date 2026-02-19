# Issue 034: Notebook `Figure` display lifecycle contract is ambiguous (`display(fig)` vs constructor autodisplay)

## Status
Open

## Summary
Notebook examples currently rely on an implicit display contract that is not fully documented: whether users should always call `display(fig)` explicitly, or whether `Figure(...)` should autodisplay by default in notebook contexts.

This question is conceptually separate from top-level `plot` symbol shadowing. Even once helper import bindings are correct, users can still encounter inconsistent behavior and confusion if notebook display expectations are not explicit and test-covered.

## Evidence
- Existing notebook quickstart snippets mix explicit display calls with context-managed plotting setup, but do not define a clear lifecycle contract.
- Open follow-up notes from Issue 033 include unresolved questions about constructor autodisplay defaults and opt-out keyword naming.
- There is no dedicated contract test that locks down notebook display behavior for `Figure` creation and first render.

## TODO
- [ ] Decide and document the public notebook display contract (`display(fig)` required vs constructor autodisplay default).
- [ ] If autodisplay is supported, define and document an idiomatic opt-out keyword/API.
- [ ] Add notebook behavior tests that verify first-render/display lifecycle under the documented contract.
- [ ] Ensure quickstart examples and notebook docs consistently follow the chosen contract.

## Exit criteria
- [ ] Notebook display lifecycle behavior is explicitly documented in toolkit docs/notebooks.
- [ ] A regression test (or small suite) enforces the chosen display contract.
- [ ] User-facing examples are consistent with tested behavior and do not rely on ambiguous implicit display semantics.
