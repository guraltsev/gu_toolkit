# Issue 030: Notebook codegen export does not preserve authoring intent for imports/defaults/symbolic literals

## Status
Open

## Summary
State-of-completion checklist:
- [ ] The Toolkit overview codegen section still documents unresolved mismatches between authored notebook code and emitted export code.
- [ ] Exported snippets are not yet validated to preserve intentional minimal imports and symbol-family authoring style.
- [ ] Exported snippets are not yet validated to avoid emitting defaults that the user did not explicitly set at call time.
- [ ] Exported snippets are not yet validated to preserve symbolic literal intent (for example `3*pi`) instead of only numericized values where possible.

## Evidence
- `docs/notebooks/Toolkit_overview.ipynb` codegen cell contains `#BUG` notes requesting:
  - import-style guidance (`from gu_toolkit import *` vs explicit SymPy prefixing),
  - SymbolFamily/FunctionFamily-aware symbol authoring,
  - omission of non-explicit defaults in generated code,
  - preservation of symbolic literal forms when inputs were authored symbolically.
- Existing bug issue `issue-025` tracks broad codegen contract alignment, but these specific authoring-fidelity behaviors are still unresolved in notebook guidance.

## TODO
- [ ] Define and document codegen fidelity policy for notebook export, including:
  - import strategy options,
  - SymbolFamily/FunctionFamily emission policy,
  - explicit-vs-implicit default argument emission,
  - symbolic literal preservation policy and known limitations.
- [ ] Implement codegen behavior (or explicit documented limitations) consistent with the above policy.
- [ ] Replace the Toolkit overview `#BUG` placeholders with finalized user-facing guidance.
- [ ] Add/extend automated regression tests in the codegen test suite to lock the policy:
  - snapshot tests for import-style variants,
  - tests that verify defaults are omitted unless explicitly set,
  - tests covering symbolic-literal preservation or explicit fallback formatting rules.
- [ ] Add notebook-driven acceptance tests that execute exported snippets and validate semantic equivalence to authored figures.

## Exit criteria
- [ ] Toolkit overview codegen section contains no placeholder BUG markers for these behaviors.
- [ ] Codegen tests and notebook acceptance tests enforce agreed authoring-fidelity behavior.
- [ ] Exported snippets and notebook guidance are consistent and reproducible.
