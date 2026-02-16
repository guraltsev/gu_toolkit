# Project 027: Configurable Figure Code Generation

**Status:** Implemented  
**Priority:** High

## Status
Implemented

## Goal/Scope
Extend figure code-generation so users can choose output style and safely preserve dynamic-info registration context in generated scripts.

## Requested Configuration Surface
Add explicit codegen options (for `Figure.to_code(...)` and lower-level helper APIs):

- `include_imports: bool = True`
  - `True`: emit imports (`import sympy as sp`, `from gu_toolkit import Figure`, etc.)
  - `False`: omit import preamble for embedding in existing scripts.
- `include_symbol_definitions: bool = True`
  - `True`: emit symbol declarations (`x = sp.Symbol("x")`, etc.)
  - `False`: assume symbols already exist in caller scope.
- `interface_style: Literal["figure_methods", "context_manager"] = "context_manager"`
  - `"figure_methods"`: generate explicit method calls (`fig.plot(...)`, `fig.info(...)`, etc.).
  - `"context_manager"`: generate context-manager style (`with fig:` then body calls) where supported.

## Dynamic Info Serialization Policy
When a registered `fig.info(...)` entry contains dynamic/callable segments:

1. Keep the registration visible in generated code as a **commented-out** `fig.info(...)` block (not silently dropped).
2. Directly below each commented dynamic-info block, emit guidance comments that:
   - call out that all referenced callable functions must be defined in scope before enabling the line,
   - suggest using introspection to print source, for example:
     - `import inspect`
     - `print(inspect.getsource(my_dynamic_func))`
3. Keep static-only info cards as active executable `fig.info(...)` calls.

## Clarified Decisions (Resolved)
1. **`interface_style` semantics**
   - Default is `"context_manager"` (`with fig:` style output).
   - `"figure_methods"` emits explicit `fig.xxx(...)` calls and preserves the same operation order.
2. **Public API surface**
   - Expose `CodegenOptions` publicly as `gu_toolkit.CodegenOptions` for discoverability and stable typing.
3. **If commented dynamic info emission is disabled**
   - Emit a **placeholder comment** (`# dynamic info omitted`) rather than silently dropping content.

## Proposed API Sketch
```python
@dataclass(frozen=True)
class CodegenOptions:
    include_imports: bool = True
    include_symbol_definitions: bool = True
    interface_style: Literal["figure_methods", "context_manager"] = "context_manager"
    include_dynamic_info_as_commented_blocks: bool = True
```

```python
def figure_to_code(snapshot: FigureSnapshot, options: CodegenOptions | None = None) -> str:
    ...
```

```python
class Figure:
    def to_code(self, *, options: CodegenOptions | None = None) -> str:
        ...
```

## Implementation Plan
- [x] Introduce `CodegenOptions` in `codegen.py` and thread options through `figure_to_code`.
- [x] Export `CodegenOptions` from package root (`gu_toolkit.CodegenOptions`).
- [x] Add conditional generation for imports and symbol declarations.
- [x] Add configurable generation mode for explicit figure-method calls vs context-manager output style.
- [x] Update dynamic-info emission:
  - [x] emit commented-out registration code for dynamic entries,
  - [x] append standardized "define callables first" and `inspect.getsource(...)` guidance comments,
  - [x] when disabled, emit placeholder comment (`# dynamic info omitted`).
- [x] Add tests for each option combination and mixed static/dynamic info cards.
- [x] Update docs with examples for notebook embedding and script embedding.

## TODO checklist
- [ ] Keep this checklist aligned with project milestones.

## Exit criteria
- [x] Users can toggle imports and symbol definitions independently.
- [x] Users can select figure-method vs context-manager interface style and get deterministic output.
- [x] Dynamic info registrations appear as commented blocks with actionable recovery guidance directly below each call.
- [x] If dynamic comments are disabled, generated output still makes omission explicit.
- [x] New tests cover configuration branches and preserve current default behavior.
