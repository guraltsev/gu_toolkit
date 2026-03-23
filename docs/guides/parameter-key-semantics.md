# Parameter key semantics

The toolkit now treats the **parameter name string** as the canonical identity
for every parameter-facing interface.

Concretely, the authoritative key is:

- `"a"`
- not the exact `sympy.Symbol("a")` object instance.

A symbol is still accepted anywhere a parameter key is expected, but the first
resolution step is always:

- `sym -> sym.name`

That rule applies consistently across:

- `Figure.parameter(...)`
- `fig.parameters[...]`
- `fig.parameters.parameter_context`
- `fig.parameters.render_parameter_context`
- `ParameterSnapshot` / `ParameterValueSnapshot`
- `NumericFunction.freeze(...)`
- `NumericFunction.unfreeze(...)`
- `NumericFunction.set_parameter_context(...)` lookups

## Practical consequences

### 1. One logical parameter per name

If two distinct SymPy symbols share the same name, they now share one logical
parameter entry:

```python
q_real = sp.Symbol("q", real=True)
q_integer = sp.Symbol("q", integer=True)

ref1 = fig.parameter(q_real)
ref2 = fig.parameter(q_integer)

assert ref1 is ref2
assert list(fig.parameters) == ["q"]
```

The first registered symbol is kept as the representative symbol for snapshot
and code-generation helpers, but lookup is driven by the shared name.

### 2. Mapping-like APIs iterate names

Parameter registries and snapshots now iterate canonical names:

```python
list(fig.parameters)                  # ["a", "b"]
list(fig.parameters.snapshot())       # ["a", "b"]
list(fig.parameters.snapshot(full=True))
```

Symbol lookup still works:

```python
fig.parameters[a] is fig.parameters["a"]
fig.parameters.snapshot()[a] == fig.parameters.snapshot()["a"]
```

### 3. NumericFunction bindings are also name-authoritative

`NumericFunction.freeze()` and `unfreeze()` now resolve symbol inputs by name
before binding. That means one binding applies to all symbols that share the
same `symbol.name`.

```python
compiled = numpify(q_real * x + q_integer, vars=(x, q_real, q_integer))
frozen = compiled.freeze({q_real: 2.0})

assert frozen.free_vars == (x,)
assert frozen(3.0) == 8.0
```

String keys are the first-class form:

```python
compiled.freeze({"q": 2.0})
compiled.unfreeze("q")
compiled.set_parameter_context({"q": 1.5})
```

For backward compatibility, `freeze()` still accepts keyed `vars=` aliases and
runtime argument names when no canonical parameter name matches the provided
string.

### 4. Explicit plot parameters expand by name

When `Figure.plot(..., parameters=...)` receives a string key, the name is
expanded against all matching symbols in the expression or numeric callable.
That keeps one logical parameter name bound to every same-name symbol used by
that plot.

## Snapshot/codegen note

`ParameterSnapshot` stores entries by parameter name, but also retains the
representative symbol for each name. Code generation uses that representative
symbol only for reproducible source output; runtime lookup still uses the name.
