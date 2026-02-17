# Issue 031: Callable `plot(..., vars=...)` mapping is too limited for notebook examples using named/indexed binding

## Status
Open

## Summary
State-of-completion checklist:
- [ ] Notebook callable example requests `vars` mappings by parameter name (for example `{'x': x, 'A': A, 'k': k[1]}`) and mixed positional/indexed forms.
- [ ] Current `plot(..., vars=...)` normalization accepts symbol or sequence of symbols, but not mapping-based argument binding.
- [ ] No regression tests currently define the supported behavior for callable argument mapping by name/index.

## Evidence
- `docs/notebooks/Toolkit_overview.ipynb` callable section includes `#BUG` guidance requesting string-key and positional-key mapping forms for `vars`.
- `Figure.py` type hints and normalization logic currently accept `vars: Optional[Union[Symbol, Sequence[Symbol]]]` and convert to tuple semantics, not dict/mapping semantics.

## TODO
- [ ] Decide callable-vars API contract:
  - support mapping-by-name only,
  - support mapping-by-position only,
  - or support both with deterministic precedence and validation rules.
- [ ] Implement the selected mapping behavior in plot input normalization.
- [ ] Add clear error messages for invalid/ambiguous mappings.
- [ ] Update notebook examples to use only supported contract and remove placeholder bug notes.
- [ ] Add comprehensive tests for this bug in callable plot test suite:
  - unit tests for mapping success paths,
  - failure tests for unknown names/indices and duplicate bindings,
  - notebook parity tests that execute the callable walkthrough cells successfully.

## Exit criteria
- [ ] Callable notebook examples run without manual workaround and without BUG placeholders.
- [ ] `plot(..., vars=...)` behavior is documented and enforced by automated tests.
- [ ] Mapping errors are actionable and deterministic.
