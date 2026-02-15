# Project 027: Configurable Figure Code Generation

**Status:** Proposal  
**Priority:** High

## Goal
Extend figure code-generation so users can choose output style and safely preserve dynamic-info registration context in generated scripts.

## Requested Configuration Surface
Add explicit codegen options (for `Figure.to_code(...)` and lower-level helper APIs):

- `include_imports: bool = True`
  - `True`: emit imports (`import sympy as sp`, `from gu_toolkit import Figure`, etc.)
  - `False`: omit import preamble for embedding in existing scripts.
- `include_symbol_definitions: bool = True`
  - `True`: emit symbol declarations (`x = sp.Symbol("x")`, etc.)
  - `False`: assume symbols already exist in caller scope.
- `infinity_style: Literal["oo", "context"] = "oo"`
  - `"oo"`: preserve direct `sp.oo` usage in generated expressions/ranges.
  - `"context"`: emit a context-manager style form using `with ..` where supported by the toolkit's generated-script conventions.

## Dynamic Info Serialization Policy (New)
When a registered `fig.info(...)` entry contains dynamic/callable segments:

1. Keep the registration visible in generated code as a **commented-out** `fig.info(...)` block (not silently dropped).
2. Directly below each commented dynamic-info block, emit guidance comments that:
   - call out that all referenced callable functions must be defined in scope before enabling the line,
   - suggest using introspection to print source, for example:
     - `import inspect`
     - `print(inspect.getsource(my_dynamic_func))`
3. Keep static-only info cards as active executable `fig.info(...)` calls.

## Proposed API Sketch
```python
@dataclass(frozen=True)
class CodegenOptions:
    include_imports: bool = True
    include_symbol_definitions: bool = True
    infinity_style: Literal["oo", "context"] = "oo"
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
- [ ] Introduce `CodegenOptions` in `codegen.py` and thread options through `figure_to_code`.
- [ ] Add conditional generation for imports and symbol declarations.
- [ ] Add configurable infinity emission mode (`sp.oo` vs context-manager output mode).
- [ ] Update dynamic-info emission:
  - [ ] emit commented-out registration code for dynamic entries,
  - [ ] append standardized "define callables first" and `inspect.getsource(...)` guidance comments.
- [ ] Add tests for each option combination and mixed static/dynamic info cards.
- [ ] Update docs with examples for notebook embedding and script embedding.

## Open Questions
- [ ] Confirm exact syntax/semantics expected for the `"context"` infinity style (single context, per-block context, or helper wrapper).
- [ ] Decide whether `CodegenOptions` should live publicly (`gu_toolkit.CodegenOptions`) or remain internal keyword options.
- [ ] Decide default behavior for dynamic info when comments are disabled (drop vs placeholder comment).

## Exit Criteria
- [ ] Users can toggle imports and symbol definitions independently.
- [ ] Users can select infinity emission style and get deterministic output.
- [ ] Dynamic info registrations appear as commented blocks with actionable recovery guidance directly below each call.
- [ ] New tests cover configuration branches and preserve current default behavior.
