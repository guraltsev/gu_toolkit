# Detailed Code Organization Review: Numeric Functions, Symbolic Functions, and Live Views

## 1) Scope and method
This review focused on the following implementation areas:
- Symbolic function definition and custom function integration (`NamedFunction.py`)
- Symbolic→numeric compilation and binding (`numpify.py`, `NumericExpression.py`)
- Live parameter/value infrastructure (`SmartFigure.py`, `ParamRef.py`, `ParamEvent.py`, `ParameterSnapshot.py`)
- Notebook-facing numeric helper layer (`prelude.py`)

The assessment criteria were:
- separation of concerns
- API clarity and consistency
- redundancy and stale code risk
- maintainability and testability

---

## 2) Architecture strengths

### 2.1 Strong symbolic customization model
`NamedFunction` cleanly supports:
- function-style symbolic definitions
- class-based symbolic+numeric specs
- optional `f_numpy` hooks
- strict signature validation

This is a meaningful strength because it gives predictable contracts for extension while still supporting rich documentation/introspection.

### 2.2 Compilation and binding are conceptually solid
`numpify.py` does several things very well:
- preserves metadata in `NumpifiedFunction` (expression, args, source)
- supports explicit and auto-discovered function bindings
- separates unbound and bound execution via `BoundNumpifiedFunction`
- distinguishes **live** (provider) and **dead** (snapshot dict) modes

This is a good foundation for interactive tools and deterministic computations.

### 2.3 Good use of protocols
`ParameterProvider` and `ParamRef` protocol usage is a good organizational move. It decouples core evaluation from specific widget classes and keeps options open for alternate controls/providers.

### 2.4 Useful snapshot semantics
`ParameterSnapshot` deep-copy behavior and read-only mapping projections reduce accidental mutation. This improves reproducibility in numerically sensitive workflows.

---

## 3) Organizational issues and critique

### 3.1 `SmartFigure.py` is overloaded
The file includes:
- context-stack helpers
- layout/widget construction
- parameter management orchestration
- plotting model and rendering
- module-level global proxies/utilities (`plot`, `parameter`, `params`, etc.)

This single-file concentration creates high cognitive load and makes change impact difficult to localize.

**Impact:** harder onboarding, more fragile refactors, and increased risk of subtle regressions.

### 3.2 Binding/evaluation logic is duplicated
There are overlapping implementations of “resolve args/params and evaluate numerically”:
- `BoundNumpifiedFunction` in `numpify.py`
- `SmartPlot._eval_numeric_live` in `SmartFigure.py`
- `_resolve_numeric_callable` + `_resolve_parameter_values` in `prelude.py`

**Impact:** semantic drift risk (e.g., edge-case handling differs across paths), and repeated bug fixes.

### 3.3 API redundancy creates ambiguity
The package intentionally exposes many aliases and convenience surfaces:
- `parameters` and `params`
- figure methods and module-level free functions
- context-driven proxies and direct object access

This is convenient for notebooks but costly in maintainability because there is no single obvious “primary path.”

### 3.4 `prelude.py` contains legacy-style import fallback repetition
Multiple functions repeat package-vs-standalone import fallbacks. This pattern is likely historical but now contributes noise and extra branches in critical helper code.

### 3.5 `ProxyParamRef` has repetitive forwarding boilerplate
`min`, `max`, `step`, and `default_value` each implement almost identical guards/get/set behavior.

**Impact:** more lines than needed, easy to introduce inconsistent behavior or docs drift.

---

## 4) Stale/redundant code candidates

These are not guaranteed dead code, but are good candidates for cleanup or consolidation.

1. **`SmartPlot._eval_numeric_live`**
   - Appears to reimplement behavior already available via provider-bound numpified functions and `PlotView`.
   - Candidate action: replace internal calls with `self._numpified.bind(self._smart_figure)` and remove bespoke loop.

2. **Repeated import fallback blocks in `prelude.py`**
   - Same pattern repeated for `numpify` and `SmartFigure` imports.
   - Candidate action: centralize in one internal helper at module import time.

3. **Module-level proxy/alias overlap**
   - Multiple paths expose the same behavior (`params`, `parameters`, free function wrappers).
   - Candidate action: document one preferred path; move compatibility aliases to a dedicated compatibility section/module.

4. **ParamRef optional-attribute forwarding repetition**
   - Mechanically repeated getter/setter and `hasattr` checks.
   - Candidate action: utility descriptor or helper to generate these properties.

---

## 5) Recommended target architecture

### 5.1 Decompose by concern
Proposed modules:
- `figure/core.py`: SmartFigure facade + render orchestration
- `figure/context.py`: current-figure stack helpers
- `figure/plots.py`: SmartPlot model and numeric-expression bridge
- `figure/parameters.py`: ParameterManager and parameter hooks
- `figure/layout.py`: UI/widget assembly
- `figure/compat.py`: module-level proxies and backward-compatible shortcuts

### 5.2 One canonical numeric evaluation pipeline
- Treat `NumpifiedFunction` + `BoundNumpifiedFunction` as the authoritative mechanism.
- `PlotView`, `SmartPlot`, and `prelude` should only compose/route through that mechanism.

### 5.3 Define API tiers explicitly
- **Tier 1 (preferred):** object-oriented entry points (`fig.parameters`, `plot.numeric_expression`, etc.)
- **Tier 2 (compat):** global proxies and aliases

Document this clearly and annotate compat APIs for eventual deprecation if desired.

---

## 6) Concrete improvements with low migration risk

1. Remove internal duplicate live-evaluation loops and call `bind(provider)` directly.
2. Consolidate prelude imports into one local resolver helper.
3. Add tests that assert behavior equality across:
   - `plot.numeric_expression(x)`
   - `plot.numpified.bind(fig)(x)`
   - prelude helper evaluation path
4. Introduce a lightweight compatibility map in docs listing preferred vs alias APIs.

---

## 7) Risks and mitigations

### Risk: breaking notebook convenience flows
- **Mitigation:** keep aliases, but isolate and test them as compatibility layer.

### Risk: behavior mismatch during consolidation
- **Mitigation:** add golden tests around binding semantics (missing params, mixed bound/free args, snapshots vs providers).

### Risk: import-path regressions
- **Mitigation:** centralize import fallback behavior once and test in both package and direct execution scenarios.

---

## 8) Bottom line
The codebase already has a solid conceptual model for symbolic definitions, compilation, and live bindings. The main issue is **organization and duplication**, not foundational design correctness. Refactoring should focus on reducing duplicated evaluation logic, shrinking `SmartFigure.py` into cohesive modules, and explicitly separating preferred APIs from compatibility conveniences.
