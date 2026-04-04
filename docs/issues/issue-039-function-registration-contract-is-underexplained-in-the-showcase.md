# Issue 039: The function-registration contract is underexplained in the showcase notebook

## Status
Open

## Summary
The notebook uses `ExpressionContext.from_symbols(..., functions=[...], include_named_functions=False)` without explaining why function names have to be passed separately, what `include_named_functions` actually does, or when other APIs such as `register_function()`, `from_expression()`, or `register_expression()` are a better choice.

As written, the example feels arbitrary even though the underlying code supports multiple, meaningfully different construction paths.

## Evidence
- Notebook cell 7 contains an explicit review note asking:
  - why functions need to be specified in the `ExpressionContext` call
  - whether that information can be deduced from the SymPy object type
- `ExpressionContext.from_symbols` accepts:
  - `symbols`
  - `functions`
  - `include_named_functions`
  (`src/gu_toolkit/mathlive/context.py:213-263`)
- Alternative API paths exist:
  - `ExpressionContext.from_expression(...)` (`src/gu_toolkit/mathlive/context.py:265-322`)
  - `ExpressionContext.register_function(...)` (`src/gu_toolkit/mathlive/context.py:464-524`)
  - `ExpressionContext.register_expression(...)` (`src/gu_toolkit/mathlive/context.py:526-550`)
- The current docstrings for these methods are boilerplate and do not answer the notebook’s question.

## TODO / Approach to solution
- Add a short conceptual explanation of why symbols and callable heads are tracked separately.
- Document `include_named_functions` clearly, especially what happens when it is `True` vs `False`.
- Decide which API path is best for a tutorial:
  - explicit registry construction,
  - register methods,
  - or expression-driven discovery.
- If the explicit `functions=[...]` path remains, justify it in the notebook text.

## Exit criteria
- A reader can explain why the example registers both symbols and functions.
- The notebook makes clear what `include_named_functions` is doing.
- The tutorial uses the least surprising construction path, or explicitly explains why a more advanced one is shown.
