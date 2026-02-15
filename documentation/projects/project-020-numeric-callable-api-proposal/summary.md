# Project 020: Numeric Callable API (Completed)

## Completion status

This project is now **fully implemented**.

## Delivered outcomes

### Canonical API migration

- `NumericFunction` is the primary numeric callable abstraction used internally.
- `numpify(...)` / `numpify_cached(...)` return `NumericFunction` instances.
- Figure and numeric helper code paths now type against `NumericFunction` directly.
- `NumpifiedFunction` remains available only as a compatibility constructor.

### Unified `vars` contract

`vars` supports all proposal forms:

1. **Pure positional** (`vars=(x, y)`)
2. **Positional + keyed tail mapping** (`vars=(x, {"y": y, "scale": s})`)
3. **Pure keyed mapping** (`vars={"x": x, "scale": s}`)
4. **Indexed positional mapping + keyed mapping** (`vars={0: x, 1: y, "scale": s}`)

Validation guarantees:

- Integer keys are contiguous from `0`.
- Non-integer keys are strings.
- Duplicate symbols are rejected.
- Argument-name normalization is deterministic and collision-safe.

### Runtime parity and round-trip semantics

- `freeze(...)` / `unfreeze(...)` / dynamic parameter binding behavior is shared across canonical and compatibility construction paths.
- `NumericFunction.vars` keeps legacy tuple-like iteration while supporting `vars()` round-trip reconstruction.
- Signature introspection (`inspect.signature`) tracks currently free variables.

### Comprehensive tests

The numeric callable API test suite now covers:

- constructor and return-type contract,
- all supported `vars` input modes,
- keyed and positional call validation,
- contiguous integer-key enforcement,
- freeze/unfreeze parity across `NumericFunction` and `NumpifiedFunction`,
- dynamic parameter-context resolution,
- free-variable/signature tracking,
- vectorized execution behavior.

## Notes

`NumpifiedFunction` is intentionally retained as a compatibility alias during migration windows, but `NumericFunction` is the canonical narrative for new code and documentation.
