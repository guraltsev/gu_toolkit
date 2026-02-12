# Numpify refactor: argument management + parameter_context (summary)

## What changes

### Compile-time argument handling
- At compilation, `numpify` determines the argument symbols in one of two ways:
  1. **Explicit**: user passes `args` (preferred when order matters).
  2. **Autodetect**: derive from the expression (see **Open decisions** for ordering rule).

- `numpify` builds a stable `call_signature`:

  ```text
  call_signature: tuple[(symbol, parameter_name), ...]   # ordered
  ```

  where `parameter_name` is a valid, unique Python identifier obtained by:
  - accepting valid identifiers directly when non-colliding;
  - mangling invalid/keyword names (e.g. `lambda -> lambda__`);
  - deconflicting duplicates (`x -> x__0, x__1, ...`);
  - ensuring no collisions with internal reserved names.

### Codegen invariants (key correctness requirement)
- The generated Python function signature uses `parameter_name`s.
- The generated function **body** must use the *same* `parameter_name`s.
- Therefore, codegen performs a **symbol replacement step**:
  - replace each original `symbol` by a fresh SymPy symbol (typically a `Dummy`) whose printed name equals the chosen `parameter_name`,
  - then print/compile the replaced expression.
- The original expression is stored in `.symbolic`.

### Binding model
- `freeze(...)` returns a **new callable** (no in-place mutation).
- Parameter values can come from three sources, in order:
  1. concrete frozen values,
  2. **dynamic** values pulled from `parameter_context`,
  3. remaining values filled from call-time positional arguments (in fixed order).

### Sentinels
- `DYNAMIC_PARAMETER`: mark a symbol as “pull from parameter_context at call time”.
- `UNFREEZE`: remove both concrete and dynamic bindings for a symbol.

### Naming
- Replace “provider” with **parameter_context**.
- `parameter_context.parameters[symbol].value` is the live-value interface (keys are SymPy symbols).

## New public surface (high level)

### On the compiled object
- `call_signature: tuple[(symbol, parameter_name), ...]`
- convenience accessors:
  - `parameters -> tuple[symbol, ...]`
  - `parameter_names -> tuple[str, ...]`
  - `symbol_for_name[name] -> symbol`
  - `name_for_symbol[symbol] -> name`

### Binding / context
- `freeze(...) -> new_bound_callable`
- `unfreeze(...) -> new_bound_callable` (thin wrapper around `UNFREEZE`)
- `set_parameter_context(ctx) -> new_bound_callable`
- `remove_parameter_context() -> new_bound_callable`

## Behavior guarantees
- A callable’s **positional call meaning is stable** and does not change when `parameter_context` starts/stops providing symbols.
- If a symbol is marked `DYNAMIC_PARAMETER`:
  - missing `parameter_context` at call time -> error,
  - missing symbol in `parameter_context.parameters` -> error,
  - the symbol is **never** filled from call-time positional arguments.

## Open decisions (must be fixed to implement)
1. Autodetect ordering rule for parameters derived from an expression (e.g. `args` omitted).  
2. Whether runtime calls should support keyword arguments (in addition to positional) and how that interacts with mangled names.
