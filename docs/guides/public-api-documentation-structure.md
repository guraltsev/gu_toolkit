# Public API documentation structure

This file defines the required shape for public function, method, and class
documentation in `gu_toolkit`.

The primary goal is **discoverability**: a user should be able to open `help(...)`
in a notebook or IDE and immediately answer all of these questions:

1. What is this API for?
2. How do I call it?
3. What do the parameters and return values mean?
4. Which optional arguments matter most?
5. Where does this API sit in the package architecture?
6. What should I read next if I want more depth?

## Required section order

Every public function, method, and class docstring should use this order:

1. one-line summary
2. `Full API`
3. `Parameters`
4. `Returns`
5. `Optional arguments`
6. `Architecture note`
7. `Examples`
8. `Learn more / explore`

These headings are intentionally uniform so users can scan quickly and so the
repository can enforce the structure with a regression test.

## Section-by-section rules

### 1. Summary line

- One clear sentence.
- Name the object’s role, not just its implementation detail.
- Prefer “Create a view”, “Return the current x-range”, or “Structured status
  record for Plotly widget support” over vague text like “Helper” or “Utility”.

### 2. Full API

- Show the user-facing call surface.
- For functions and regular methods, show the call signature.
- For properties, show `obj.attr` or `obj.attr = value` rather than the hidden
  implementation signature.
- For classes, show the constructor signature and list the public members that
  make the class discoverable.

### 3. Parameters

- List every parameter with type information and meaning.
- Explicitly mark whether it is required or optional.
- Explain *what the parameter means in toolkit terms*, not just its Python type.
- For forwarded `**kwargs`, say that they are forwarded and point readers to the
  relevant guide or runtime-discovery helper.

### 4. Returns

- Always describe the return value.
- If the API returns `None`, say so explicitly and explain that the call is for
  side effects or scheduling.
- For protocol/interface classes, explain that callers provide an implementation
  that satisfies the protocol.

### 5. Optional arguments

- Call out every optional parameter with its default.
- Mention behavior-changing flags, forwarded keywords, compatibility aliases,
  and anything that readers should not have to infer from the signature alone.
- Do not assume that the `Parameters` section is enough; this section is for
  emphasis and quick scanning.

### 6. Architecture note

- Explain who owns the state and why this API exists.
- Mention whether the API is a coordinator surface, a delegating convenience
  wrapper, a renderer-specific helper, or a boundary object such as a snapshot.
- The architecture note should help maintainers avoid bypassing the intended
  owner object.

### 7. Examples

Every public docstring should include at least two mini-scenarios:

- **basic use**: the most direct call or construction pattern
- **discovery-oriented use**: `help(...)`, `dir(...)`, or a closely related
  object that users should inspect next

The examples do not need to be large; they need to make the next step obvious.

### 8. Learn more / explore

This section is required for discoverability.

It should include some mix of:

- `docs/guides/api-discovery.md`
- the most relevant design guide
- a matching example notebook
- a matching regression/spec test
- a notebook/REPL discovery tip such as `plot_style_options()` or `dir(fig)`

## Discoverability rules

1. Prefer stable owner objects as entry points (`Figure`, `View`, `ParameterManager`, `Plot`, snapshots).
2. Mention runtime discovery helpers when they exist:
   - `plot_style_options()`
   - `field_style_options()`
   - `field_palette_options()`
   - `help(...)`
   - `dir(...)`
3. Cross-link to the exact guide/example/test that gives the next level of detail.
4. When a new public API family appears, update `docs/guides/api-discovery.md`.
5. When a new public function/class/method is added, update its docstring in the
   same commit as the implementation.

## Class-specific guidance

For classes, the docstring should make three things obvious:

- how the class is constructed,
- which public members are worth inspecting next,
- whether the class is a concrete owner object, a lightweight record/snapshot,
  or a protocol/interface.

## Maintenance note

The repository includes a regression test that checks the public docstring
structure. If you change the headings here, update the test and the source
writer together.
