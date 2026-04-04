# Issue: The tutorial underexplains why function names are registered separately and what `include_named_functions` means

## Summary
The showcase builds an `ExpressionContext` with both symbols and functions, but it does not clearly explain the rule being taught: symbols and callable heads are separate semantic categories, and the context tracks them separately on purpose.

As written, the example can feel arbitrary because readers are shown one specific constructor call without being told why it is shaped that way or when the alternative APIs are better.

## Evidence
- Notebook cell 11 uses:
  - `ExpressionContext.from_symbols(...)`
  - `functions=[Force, 'Force_t', 'Force__x']`
  - `include_named_functions=False`
- The surrounding notebook text does not explain why `Force` must be registered as a function instead of being inferred automatically from the displayed expression example.
- `src/gu_toolkit/mathlive/context.py:271-341` shows that `ExpressionContext.from_symbols()` accepts separate `symbols`, `functions`, and `include_named_functions` inputs, and then registers them through distinct code paths.
- `src/gu_toolkit/mathlive/context.py:343-399` provides `from_expression(...)` as a second construction path that can infer context from an existing SymPy expression.
- `src/gu_toolkit/mathlive/context.py:523-592` provides `register_symbol(...)` and `register_function(...)`, and `register_named_functions()` imports the global `NamedFunction` registry.
- The tutorial does not explain when a reader should prefer:
  - explicit `functions=[...]`
  - `include_named_functions=True`
  - `from_expression(...)`
  - or incremental `register_function(...)`

## TODO / Approach to solution
- Add one short conceptual explanation: symbols are atomic names, functions are callable heads, and the parser/rendering/transport need to know the difference.
- Explain what `include_named_functions` does in practical terms.
- Decide on one tutorial path and justify it. For example, either use the most explicit constructor for teaching, or use the most natural constructor for users.
- Keep alternative APIs in a short "other ways to build the context" note rather than leaving them implicit.

## Exit criteria
- A reader can explain why functions are registered separately from symbols.
- The role of `include_named_functions` is clear without source diving.
- The tutorial's chosen construction path feels intentional rather than arbitrary.
