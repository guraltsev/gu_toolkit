# Project 023: Package Reorganization

**Status:** Backlog
**Priority:** Medium

## Goal/Scope

Reorganize the flat 29-module layout into focused subpackages that codify
the layered architecture already present by convention. The public API
(`from gu_toolkit import ...`) must remain unchanged throughout migration.

## Context

The codebase has a clear conceptual layering (math engine → parameter
management → plot orchestration → UI widgets → public API → serialization)
but all 29 modules live in a single flat directory. This makes it
difficult for new contributors to build a mental model, clutters IDE
navigation, and prevents enforcing boundaries between layers.

Additionally, 4 backward-compatibility shims (`prelude.py`,
`prelude_extensions.py`, `prelude_support.py`, `numeric_callable.py`)
exist as pure re-export modules and should be consolidated with
deprecation warnings.

File naming is inconsistent: most modules use `snake_case` but 7 use
`PascalCase` (`Figure.py`, `Slider.py`, `NamedFunction.py`, `ParamRef.py`,
`ParseLaTeX.py`, `InputConvert.py`, `PlotlyPane.py`).

## Proposed subpackage structure

```
gu_toolkit/
├── core/                    # Protocols, events, state, utilities
│   ├── param_event.py       # ParamEvent
│   ├── param_ref.py         # ParamRef, ProxyParamRef
│   ├── parameter_snapshot.py
│   ├── context.py           # figure_context → context
│   ├── input_convert.py     # InputConvert → input_convert
│   └── debouncing.py
│
├── figure/                  # Figure orchestration and components
│   ├── core.py              # Figure class
│   ├── api.py               # Module-level helpers (from project-022)
│   ├── layout.py            # FigureLayout, OneShotOutput
│   ├── parameters.py        # ParameterManager
│   ├── info.py              # InfoPanelManager
│   ├── legend.py            # LegendPanelManager
│   ├── plot.py              # Plot, PlotHandle
│   └── view.py              # View dataclass
│
├── math/                    # Symbolic and numeric engine
│   ├── numpify.py           # numpify, NumericFunction
│   ├── named_function.py    # NamedFunction
│   ├── operations.py        # NIntegrate, Fourier, play
│   ├── latex.py             # parse_latex, LatexParseError
│   └── extensions.py        # SymbolFamily, FunctionFamily, Infix
│
├── widgets/                 # UI components
│   ├── slider.py            # FloatSlider
│   └── plotly_pane.py       # PlotlyPane
│
├── snapshot/                # Serialization and reproducibility
│   ├── figure_snapshot.py   # FigureSnapshot
│   ├── plot_snapshot.py     # PlotSnapshot
│   └── codegen.py           # Code generation
│
├── notebook_namespace.py    # Star-import convenience namespace
└── __init__.py              # Unchanged public API re-exports
```

## Migration strategy

1. **Migrate lowest-risk modules first:** `math/` and `widgets/` are
   self-contained with minimal internal dependents.
2. **Then `core/`:** Protocols and events are imported widely but have no
   circular dependencies.
3. **Then `snapshot/`:** Serialization layer depends on core but not on
   figure.
4. **Then `figure/`:** Depends on project-022 completing the Figure
   decomposition first.
5. **At each step:** Move module, update internal imports, add re-export in
   `__init__.py`, run full test suite.
6. **Normalize to snake_case** during each move (e.g., `ParseLaTeX.py` →
   `math/latex.py`).
7. **Deprecate shims:** Add `DeprecationWarning` to `prelude.py`,
   `prelude_extensions.py`, `prelude_support.py`, and
   `numeric_callable.py`. Remove after one release cycle.

## TODO checklist

- [ ] Draft no-break public API compatibility matrix.
- [ ] Migrate `math/` subpackage (lowest risk, self-contained).
- [ ] Migrate `widgets/` subpackage.
- [ ] Migrate `core/` subpackage.
- [ ] Migrate `snapshot/` subpackage.
- [ ] Migrate `figure/` subpackage (after project-022).
- [ ] Normalize all module names to snake_case during moves.
- [ ] Add deprecation warnings to backward-compatibility shims.
- [ ] Update test imports to use new paths.
- [ ] Verify `__init__.py` re-exports preserve public API.

## Exit criteria

- [ ] All modules are organized into subpackages by responsibility.
- [ ] Public API (`from gu_toolkit import ...`) is unchanged.
- [ ] All module names follow snake_case convention.
- [ ] Backward-compatibility shims emit deprecation warnings.
- [ ] Test suite passes throughout and after migration.

## Dependencies

- **project-022 (Figure Decomposition):** The `figure/` subpackage
  migration is cleanest after Figure.py is decomposed. Other subpackages
  can proceed independently.
- **project-021 (Packaging Hardening):** The flat-vs-`src/` layout
  decision should be resolved here; project-021 documents the convention.

## Challenges and mitigations

- **Challenge:** Internal imports between modules change during migration.
  **Mitigation:** Move one subpackage at a time; run full test suite after
  each move; use `__init__.py` re-exports as a safety net.

- **Challenge:** External users may import internal paths.
  **Mitigation:** Only the `__init__.py` re-exports are the public API.
  Document this clearly.

- **Challenge:** PascalCase → snake_case rename may break existing
  references in notebooks and documentation.
  **Mitigation:** Re-export old names during transition; search and update
  all notebooks and docs.

## Completion Assessment (2026-02-18)

- [ ] Repository still uses a flat module layout at package root; proposed `core/`, `figure/`, `math/`, `widgets/`, and `snapshot/` subpackages are not yet migrated.
- [ ] PascalCase module filenames are still present (`Figure.py`, `Slider.py`, `NamedFunction.py`, etc.).
- [ ] Backward-compatibility shim deprecation warnings have not been introduced for re-export modules.
- [ ] Import-path migration and compatibility-matrix work have not yet started.

**Result:** Project remains **open**. This reorganization has not yet been implemented.
