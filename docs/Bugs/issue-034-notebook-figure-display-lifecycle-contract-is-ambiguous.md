# Issue 034: Notebook `Figure` display lifecycle contract is ambiguous (`display(fig)` vs constructor autodisplay)

## Status
Open

## Summary
Notebook examples currently rely on an implicit display contract that is not fully documented: whether users should always call `display(fig)` explicitly, or whether `Figure(...)` should autodisplay by default in notebook contexts.

Users can encounter inconsistent behavior and confusion if notebook display expectations are not explicit and test-covered.

## Evidence
- There is no dedicated contract test that locks down notebook display behavior for `Figure` creation and first render.

## TODO
- [ ] Document that the constructor does not display by default displays.  
- [ ] If autodisplay is supported, and is enabled using the display=True parameter.
- [ ] Add tests that verify first-render/display lifecycle under the documented contract.

## Exit criteria
- [ ] Notebook display lifecycle behavior is explicitly documented in toolkit docs/notebooks.
- [ ] A regression test (or small suite) enforces the chosen display contract.
- [ ] User-facing examples / documentation are consistent with tested behavior and do not rely on ambiguous implicit display semantics.
