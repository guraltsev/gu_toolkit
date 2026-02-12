# Blueprint: Numpify refactor (argument management + parameter_context)

## 0. Goals

1. **Correct code generation** with Python-safe parameter names.
2. **Stable calling semantics** independent of `parameter_context` churn.
3. **Explicit dynamic lookup** via `DYNAMIC_PARAMETER` (no implicit “fill from context if available”).
4. **Discoverable API**: use the name `parameter_context` rather than “provider”.
5. Preserve the ability to store and expose the original SymPy expression in `.symbolic`.

Non-goals:
- No performance micro-optimizations beyond avoiding obvious regressions.
- No broad redesign of SymPy printing beyond what is needed to ensure identifier correctness.

## 1. Current state (observed from `numpify.py`)

- `NumpifiedFunction` stores `expr`, `args: tuple[Symbol, ...]`, `source`, and calls an internal compiled `_fn` with positional args.
- `BoundNumpifiedFunction` supports:
  - **snapshot** mode: dict[Symbol, value] mapped into argument slots;
  - **live** mode: reads *trailing* values from a live object via `provider.params[sym].value` and assumes call-time args fill a prefix.

Limitations motivating refactor:
- Generated code currently uses `symbol.name` in the function signature; invalid identifiers / collisions are not handled.
- Live binding assumes a prefix/suffix split and cannot support arbitrary freezing/dynamic-per-symbol policies.
- The term “provider” is not preferred; we want `parameter_context`.

## 2. New terminology and sentinels

### 2.1 `parameter_context`
A live object providing parameter values:

- required interface (conceptual):
  - `parameter_context.parameters: Mapping[Symbol, Any]`
  - where `parameter_context.parameters[sym].value` is the current value.

### 2.2 Sentinels
Introduce module-level singleton sentinels:

- `DYNAMIC_PARAMETER`: indicates “fetch from parameter_context at call time”.
- `UNFREEZE`: indicates “remove any concrete/dynamic binding”.

Rationale:
- `None` remains a legitimate concrete value.
- Call semantics remain explicit.

## 3. Compile-time signature: `call_signature`

### 3.1 Inputs
- `expr: sympy.Basic`
- `args` optional:
  - If provided: the ordered tuple of symbols.
  - If omitted: autodetect from `expr` (see §10 Open decisions).

### 3.2 Output structure
Store:

- `call_signature: tuple[(Symbol, str), ...]`  (ordered)
- mappings:
  - `name_for_symbol: dict[Symbol, str]`
  - `symbol_for_name: dict[str, Symbol]`

Expose convenience properties:
- `parameters: tuple[Symbol, ...]`
- `parameter_names: tuple[str, ...]`

### 3.3 Parameter name validity and mangling
For each symbol:
1. start from a base candidate name (typically `symbol.name`);
2. if not a valid Python identifier or is a keyword -> mangle (e.g. add `__`, repeat if needed);
3. if collides with previously assigned names -> add suffix `__0`, `__1`, ...;
4. avoid collisions with a reserved-name set:
   - Python keywords and builtins you rely on
   - names injected into the generated code namespace (e.g. `np`, helpers, etc.)
5. finalize the unique `parameter_name`.

Implementation note:
- Use a single “fresh name generator” that loops until it finds a name not in the forbidden set.

## 4. Code generation: replacement step (required)

### 4.1 Invariant
The compiled function’s signature parameters **must exactly match** the identifiers used in the function body.

### 4.2 Replacement mapping
Construct `sym_to_codegen_sym: dict[Symbol, Symbol]` where:

- `sym_to_codegen_sym[sym] = Dummy(parameter_name)` (or an equivalent SymPy symbol that prints as `parameter_name`).

Then build:
- `expr_codegen = expr.xreplace(sym_to_codegen_sym)` (or `subs` if required by SymPy behavior).

Store:
- `.symbolic = expr` (original)
- optionally `.expr_codegen` (for debugging) or store the mapping (preferred).

### 4.3 Printing and compilation
- Print `expr_codegen` to a NumPy-compatible code string.
- Generate Python source that defines `_generated(<parameter_names...>): return <code>`.
- `exec` the source in a namespace containing `np` and any custom function bindings.

## 5. Object model

### 5.1 `NumpifiedFunction`
Fields (conceptual):
- `_fn: Callable`
- `symbolic: sympy.Basic`
- `call_signature: tuple[(Symbol, str), ...]`
- `source: str` (generated code)
- mapping dicts for name/symbol lookups

Methods / properties:
- `__call__(*args)` remains “fully positional” (expects full arity).
- `freeze(...) -> BoundNumpifiedFunction` (returns new bound callable)
- `set_parameter_context(ctx) -> BoundNumpifiedFunction`
- `remove_parameter_context() -> BoundNumpifiedFunction` (if already none, returns self or a semantically equivalent object)

### 5.2 `BoundNumpifiedFunction` (new binding class)
Fields (conceptual):
- `parent: NumpifiedFunction`
- `_parameter_context: ParameterContext | None`
- `_frozen: dict[Symbol, Any]` (concrete values)
- `_dynamic: set[Symbol]` (symbols marked DYNAMIC_PARAMETER)

Derived:
- `free_parameters`: ordered tuple of symbols in `parent.parameters` that are neither frozen nor dynamic.
- `free_call_signature`: ordered tuple of `(sym, parent.name_for_symbol[sym])` restricted to `free_parameters`.

## 6. Binding API details

### 6.1 `freeze(...)` accepted inputs
Supports exactly one of:
- a dict mapping keys to values,
- or a list/tuple of pairs,
- or kwargs (`name=value`) with names being **mangled parameter_name** strings.

Key resolution:
- if key is `Symbol`: use it directly;
- if key is `str`: interpret as `parameter_name` and map via `symbol_for_name[name]`;
- otherwise error.

Conflicts:
- within a single `freeze` call, if the same symbol is specified more than once (via Symbol or via name), raise.

Overwrite policy:
- `freeze` overrides existing bindings from the prior bound callable (because it returns a new one).

Value rules:
- `value is DYNAMIC_PARAMETER`:
  - add symbol to `_dynamic`
  - remove symbol from `_frozen` if present
- `value is UNFREEZE`:
  - remove symbol from `_dynamic` and `_frozen`
- otherwise:
  - set `_frozen[symbol] = value`
  - remove symbol from `_dynamic` if present

### 6.2 `unfreeze(...)`
Convenience method:
- `unfreeze(*keys)` is equivalent to `freeze({key: UNFREEZE, ...})` after key resolution.

### 6.3 `set_parameter_context(ctx)` / `remove_parameter_context()`
- Non-mutating: return a new bound callable with `_parameter_context` set/cleared.
- Detach does **not** snapshot values; it merely removes the live lookup mechanism.

## 7. Call semantics (core)

Given:
- ordered `parent.parameters = (s0, s1, ..., s_{n-1})`
- ordered `free_parameters` computed from bindings

At call-time:
1. Build an array `full_values` length `n`.
2. For each symbol `s_i`:
   - if `s_i in _frozen`: `full_values[i] = _frozen[s_i]`
   - elif `s_i in _dynamic`:
     - require `_parameter_context` not None else raise
     - require `s_i in _parameter_context.parameters` else raise
     - `full_values[i] = _parameter_context.parameters[s_i].value`
   - else mark slot as “needs call arg”
3. Fill “needs call arg” slots in the order induced by `parent.parameters`, consuming `*positional_args` sequentially.
4. If not enough positional args -> raise with a message listing missing symbols/names.
5. If extra positional args remain -> raise.

Critical stability rule:
- A symbol in `_dynamic` is **never** filled from call positional args.

## 8. Error reporting requirements

Provide errors that name both:
- the SymPy symbol (repr/name) and
- the user-facing parameter_name (mangled name).

Cases:
- unknown `parameter_name` string in freeze/unfreeze/kwargs
- conflicts within a freeze call
- missing parameter_context for dynamic symbol(s)
- missing symbol key in parameter_context.parameters
- wrong arity at call-time (too few / too many)

## 9. Migration plan from current API

### 9.1 Keep backward-compatible aliases (optional but recommended)
- Keep `bind(...)` as an alias:
  - `bind(dict)` -> `freeze(dict)` (concrete freezes)
  - `bind(parameter_context)` -> `set_parameter_context(ctx)`
  - `bind(None)` -> current-figure context (if you still want this convenience)
- Deprecate `.params` name in favor of `.parameters` via an adapter, if needed.

### 9.2 Replace current `BoundNumpifiedFunction` logic
- Remove the “prefix call args + trailing provider values” approach.
- Replace with the new per-symbol `_frozen` + `_dynamic` model.

## 10. Test plan

1. **Identifier mangling**
   - keyword symbol: `Symbol("lambda")` -> `lambda__`
   - invalid identifier: `Symbol("x-y")` -> mangled valid name
   - collisions: two symbols with same `.name` produce `x__0`, `x__1`, and evaluation matches mapping

2. **Replacement step correctness**
   - confirm generated source references only parameter_names and compiles successfully

3. **Freeze semantics**
   - concrete freeze removes from free_parameters
   - `DYNAMIC_PARAMETER` marks dynamic and removes concrete
   - `UNFREEZE` clears both
   - overrides across successive freeze calls behave as specified

4. **parameter_context live values**
   - dynamic symbols read `.value` at call time
   - changing `.value` changes outputs without recompiling

5. **Stability**
   - a callable’s required positional signature is stable even if parameter_context.parameters keys change
   - dynamic symbol missing in context triggers error (no fallback to positional)

6. **Detach**
   - removing parameter_context then calling with dynamic symbols raises as expected
   - unfreezing dynamic symbols restores them to call-supplied

## 11. Implementation checklist (incremental steps)

1. Add sentinels: `DYNAMIC_PARAMETER`, `UNFREEZE`.
2. Introduce `ParameterContext` protocol with `.parameters` (keyed by Symbol) and `.value`.
3. Add compile-time `call_signature` + mangling + reserved-name handling.
4. Add expression replacement mapping and ensure printer uses the replaced expression.
5. Update `NumpifiedFunction` to store `.symbolic`, `call_signature`, and mappings.
6. Implement new `BoundNumpifiedFunction` (or rename) with `_frozen`, `_dynamic`, `_parameter_context`.
7. Implement `freeze`, `unfreeze`, `set_parameter_context`, `remove_parameter_context`.
8. Replace old live/snapshot evaluation code paths.
9. Add tests (unit tests first; then integration tests with Figure/current context if applicable).
10. Update docs and any call sites in the rest of the codebase.

## 12. Open decisions (required before coding)

1. **Autodetect parameter ordering** when `args` is omitted.
   - Need a deterministic rule (document it and test it).
2. **Runtime keyword calls**: whether to support `f(x=..., y=...)` with mangled names, or keep runtime calls positional-only.
