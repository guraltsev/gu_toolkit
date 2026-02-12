# Numeric/Symbolic Functions + Live Views — Refactor Summary

## Scope reviewed
- Numeric compilation/binding: `numpify.py`, `NumericExpression.py`
- Symbolic function authoring: `NamedFunction.py`
- Live view + parameter plumbing: `SmartFigure.py`, `ParamRef.py`, `ParamEvent.py`, `ParameterSnapshot.py`, and the numeric convenience layer in `prelude.py`

## What is working well
1. **Clear symbolic → numeric pipeline**
   - `NamedFunction` provides a disciplined way to define symbolic and numeric behavior for custom SymPy functions.
   - `numpify`/`numpify_cached` cleanly compile expressions and retain metadata through `NumpifiedFunction`.
2. **Strong live/dead binding model**
   - `BoundNumpifiedFunction` distinguishes provider-backed live evaluation from snapshot-bound deterministic evaluation.
   - `SmartPlot.numeric_expression` exposing `PlotView` is a useful “live numeric view” abstraction.
3. **Good protocol orientation**
   - `ParameterProvider` and `ParamRef` protocols reduce hard coupling and keep UI concerns somewhat swappable.
4. **Good defensive validation**
   - Signature checks in `NamedFunction`, key validation in `bind`, and unbound symbol/function checks in `numpify` are robust.

## Organizational critique
1. **SmartFigure is still too large and multi-purpose**
   - It mixes layout/UI concerns, parameter orchestration, plotting, context stack management, and module-level convenience API.
   - This hurts discoverability and makes live-view behavior harder to reason about.
2. **Live-binding rules are duplicated in multiple layers**
   - `numpify.bind`, `SmartPlot._eval_numeric_live`, and `prelude._resolve_numeric_callable` all implement overlapping “resolve values and call numeric function” logic.
3. **Public surface area is broad and partially redundant**
   - `parameters` and `params` aliases, plus module-level proxy objects and helper functions, are convenient but make ownership unclear.
4. **Prelude has import-fallback and coercion logic that repeats core behaviors**
   - The same dependency-loading blocks and binding normalization patterns reappear in several functions.

## Likely stale or redundant code candidates
1. **`SmartPlot._eval_numeric_live`** appears redundant with `self._numpified.bind(self._smart_figure)` / `PlotView.__call__` semantics.
2. **Repeated import-fallback blocks in `prelude.py`** (`try: from .x ... except ImportError: from x ...`) look legacy and repeated.
3. **Duplicate figure access APIs** (`current_figure`, `_require_current_figure`, module-level proxies/functions) create overlapping entry points.
4. **High-volume repetitive capability forwarding in `ProxyParamRef`** (`min`, `max`, `step`, `default_value`) is functional but verbose and maintenance-heavy.

## Recommended improvements (priority order)
1. **Split SmartFigure into focused modules/classes**
   - Keep `SmartFigure` facade, extract: context stack, parameter manager, plot model, and layout/view code into separate files.
2. **Establish one canonical binding/evaluation path**
   - Prefer `NumpifiedFunction` + `BoundNumpifiedFunction` as single source of truth.
   - Convert `SmartPlot` and `prelude` helpers to call that path instead of duplicating resolution logic.
3. **Reduce API redundancy with explicit compatibility layer**
   - Keep aliases/proxies but isolate them in a dedicated “compat” module and mark preferred APIs in docs.
4. **Refactor `prelude.py` imports and normalization helpers**
   - Centralize dependency resolution utilities once per module.
5. **Reduce boilerplate in `ProxyParamRef`**
   - Consider descriptor/helper-based optional-attribute forwarding to avoid repeating near-identical getter/setter blocks.

## Suggested incremental plan
- **Phase 1 (safe):** remove internal duplication (`_eval_numeric_live`, prelude helper duplication), add tests around behavior parity.
- **Phase 2 (structural):** split `SmartFigure.py` into modules with no public API changes.
- **Phase 3 (API hygiene):** document preferred paths, deprecate secondary aliases/proxies over time.
