# Semantic math refactoring philosophy

This guide records the design intent behind the refactor that split the
identifier system and the MathLive input layer into dedicated subpackages.
Future refactors should preserve these ideas even if file names or APIs evolve.

## Scope of this slice

Two areas are treated as one coherent subsystem:

1. the **canonical identifier system**
2. the **figure-independent MathLive input stack**

They now live in these canonical locations:

- `src/gu_toolkit/identifiers/`
  - `policy.py` — canonical identifier validation, parsing, rendering, symbol
    helpers, and LaTeX overrides
- `src/gu_toolkit/mathlive/`
  - `context.py` — explicit symbol/function registry plus parsing/rendering glue
  - `transport.py` — MathJSON manifest building and backend conversion helpers
  - `inputs.py` — public notebook-facing widgets (`ExpressionInput`,
    `IdentifierInput`)
  - `widget.py` — low-level MathLive-backed widget backend

Legacy modules such as `gu_toolkit.identifier_policy` and
`gu_toolkit.math_inputs` remain as **compatibility re-exports**. They should be
kept thin and boring.

## Why the split exists

Before this refactor, the relevant code lived at the top level beside many
unrelated figure and rendering modules. That made the public structure hard to
understand and encouraged cross-layer coupling.

The split exists so the code layout itself explains the architecture:

- identifier semantics are their own concern
- MathLive widgets and transport are their own concern
- figure editors consume those layers but do not define them

## Core principles

### 1. Canonical identifiers are the source of truth

A symbol or function is identified by a validated canonical string such as:

- `velocity`
- `theta_x`
- `theta__x`
- `a_1_2`
- `Force_t`

Do **not** store display LaTeX as the identity. LaTeX is presentation, not
semantic identity.

### 2. Display is derived at the boundary

Rendering helpers such as `identifier_to_latex()`, `function_head_to_latex()`,
and `render_latex()` should derive display forms from canonical names.

If a feature proposal requires storing both a canonical name and an unrelated
presentation name as equal peers, treat that as a design smell and justify it
explicitly.

### 3. MathLive widgets are figure-free

`ExpressionInput`, `IdentifierInput`, `ExpressionContext`, and the MathJSON
transport helpers belong to a **general semantic math layer**, not to the plot
editor or `Figure`.

Figure-centric code may compose these widgets, but it should not own their core
semantics.

### 4. Prefer MathJSON over ad-hoc string guessing

When MathLive can provide MathJSON, treat it as the preferred backend transport.
LaTeX and plain-text parsing remain useful as fallback and for user-facing
examples, but structured transport is easier to validate and easier to test.

### 5. Ambiguity should fail early

If the backend cannot tell whether a name is semantically meaningful, it should
raise at the semantic boundary instead of guessing.

Example: a transport name like `theta_x` is ambiguous without a context that
explicitly registers it as atomic. The correct behavior is to reject it unless
the context resolves the ambiguity.

### 6. Context must be explicit

`ExpressionContext` is the place where the backend decides which names are
atomic, which functions are callable, and which display forms belong to those
names. Avoid hidden global registries or figure-specific side channels.

### 7. Tests and notebooks are part of the architecture

The semantic math slice now has a dedicated test folder:

- `tests/semantic_math/`

Those tests are intentionally explanatory and should stay that way.

The showcase notebooks are also part of the contract:

- `examples/MathLive_identifier_system_showcase.ipynb`
- `examples/Robust_identifier_system_showcase.ipynb`

They should remain markdown-heavy, minimal in code, and runnable as lightweight
integration examples.

## Refactoring checklist for future changes

When touching this subsystem, verify all of the following:

1. Is the canonical identifier still obvious and validated in one place?
2. Is display still derived from canonical identity rather than stored as a
   competing source of truth?
3. Does the MathLive layer remain reusable outside figure code?
4. Does structured transport remain preferred when available?
5. Are ambiguous cases rejected or resolved through explicit context?
6. Were both the focused tests and the showcase notebooks updated together?
7. If a legacy wrapper changed, did it remain a thin compatibility layer rather
   than growing new logic?

## Anti-patterns to avoid

- letting `Figure`-specific state leak into `ExpressionInput` semantics
- encoding meaning only in display LaTeX
- adding new transport heuristics that silently guess ambiguous identifiers
- scattering identifier validation rules across multiple modules
- turning showcase notebooks into long dumps of code with very little
  explanation

## Recommended import style

For new internal code, prefer the canonical subpackage imports:

```python
from gu_toolkit.identifiers import parse_identifier, render_latex, symbol
from gu_toolkit.mathlive import ExpressionContext, ExpressionInput, IdentifierInput
```

Legacy imports remain valid for compatibility, but new code should use the
subpackage layout so the architecture stays visible in the import graph.
