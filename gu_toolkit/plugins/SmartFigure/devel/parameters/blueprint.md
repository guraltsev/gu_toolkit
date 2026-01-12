## OUTPUT PART 1 — Technical blueprint

### 0) Current code reality (what we’re changing)

* `SmartFigure._resolve_symbol()` currently **rejects** the “parameterized constant” case: if `expr.free_symbols` is nonempty and you pass a different `symbol`, it raises an error. 
* `Plot` currently compiles with `numpify(..., args=[symbol])`, so plots can only depend on the independent variable. 
* `Plot.compute_data()` requires `x.shape == y.shape`; constant expressions would produce a scalar `y`, which would fail that check unless we broadcast. 
* `SmartFigure.widget` currently builds `VBox([backend.fig])` (no slider UI). 
* `SmartParameter` currently notifies on `value` change, but `min_val/max_val` are plain attributes (no dynamic notification), and there is no `what_changed` tuple contract yet.  
* `numpify()` defaults to sorting `expr.free_symbols` alphabetically when `args is None`, so we **must** pass explicit `args=(symbol, *params)` for deterministic calling conventions with `symbol` first. 

---

### 1) High-level goal

Enable `SmartFigure` plots whose data depends on **parameters** detected from a SymPy expression. Parameters are managed by a registry, controlled by sliders in the figure UI, and changing a parameter recomputes **only** the plots that depend on it.

---

### 2) Expression analysis: independent variable and parameters

#### 2.1 Rules (exactly as specified)

Let `S = expr.free_symbols`.

**Independent variable selection**

* If `|S| > 1`: user **must** pass `symbol=...`.
* If `|S| = 1`:

  * If `symbol` is not specified: that single symbol is the independent variable.
  * If `symbol` *is specified* and is *different* from the single free symbol: treat as a **parameterized constant** in `symbol`.
* If `|S| = 0`: treat as a **constant** expression.

**Parameters**

* All free symbols other than the independent `symbol` are parameters.

#### 2.2 Implementation: one helper that returns a complete analysis

Introduce a helper on `SmartFigure` (or module-level) that returns:

* `independent_symbol: sympy.Symbol`
* `param_symbols_sorted: tuple[sympy.Symbol, ...]` (sorted alphabetically by `.name`)
* `kind: Literal["constant","regular","parameterized_constant"]` (optional but useful for docs/debug)

Pseudocode:

```python
def analyze_expr(expr: sympy.Expr, requested: sympy.Symbol | None, default: sympy.Symbol):
    S = expr.free_symbols

    if len(S) == 0:
        sym = requested or default
        return sym, (), "constant"

    if len(S) == 1:
        only = next(iter(S))
        if requested is None:
            return only, (), "regular"
        if requested == only:
            return requested, (), "regular"
        # parameterized constant
        return requested, (only,), "parameterized_constant"

    # len(S) > 1
    if requested is None:
        raise GuideError("Expression has multiple symbols...", hint="Specify 'symbol=...' explicitly.")
    if requested not in S:
        raise GuideError("Requested symbol ... is not in expression ...", hint="...")
    params = tuple(sorted((S - {requested}), key=lambda s: s.name))
    return requested, params, "regular"
```

This replaces the current behavior that errors out when `|S|=1` and `requested != only`. 

---

### 3) Deterministic argument order and evaluation contract

#### 3.1 Ordering

For each plot:

* Store `symbol` and `param_symbols_sorted = sorted(params, key=lambda s: s.name)`.
* Compile with:

  * `args = (symbol, *param_symbols_sorted)`

This is required because `numpify()` auto-orders all free symbols alphabetically when `args` is omitted. 
So we must **explicitly** put `symbol` first.

#### 3.2 Plot evaluation call signature

Compiled function signature:

* `f(symbol, *params_sorted_by_name)`

At evaluation time, call:

* `y = f(x_values, *[registry[p].value for p in params_sorted_by_name])`

---

### 4) Registry integration

#### 4.1 Registry selection

* Add to `SmartFigure.__init__`:

  * `parameter_registry: SmartParameterRegistry | None = None`
* Add to `SmartFigure` class:

  * `default_parameter_registry: SmartParameterRegistry` (class-level singleton)
* Effective registry:

  * `self._registry = parameter_registry or SmartFigure.default_parameter_registry`

#### 4.2 Parameter creation / reuse

When a plot analysis yields parameters:

* For each param symbol `p`:

  * If registry already has it: reuse.
  * Else create with defaults:

    * `value=0`
    * `min=-1`, `max=1`
    * `step=(max-min)/200`
* **Retention policy**: never remove parameters from the registry (even if unused by any current plot).

> Note: `SmartParameterRegistry` is already designed as an “auto-vivifying container”. 
> We’ll extend/standardize “auto-vivify” so it also sets `step` consistently for newly created parameters.

---

### 5) SmartParameter contract upgrades (dynamic min/max + `what_changed`)

#### 5.1 Required semantics

* `value`, `min`, `max` are **dynamic**: changing any notifies observers.
* Every callback receives `what_changed` as a **tuple** containing **everything** that changed in that operation:

  * `("value",)`
  * `("min","max")`
  * `("max","value")` if changing max clamps value
* Clamping rule:

  * If changing min/max clamps the current value, include `"value"` in `what_changed`.

#### 5.2 Implementation choices

**A. Keep existing callback system and add structured kwargs**
Callbacks already support flexible signatures and kwargs forwarding. 
So implement:

* `SmartParameter.value` setter calls `_notify(..., what_changed=("value",))`
* Add properties for `min_val` and `max_val` (or keep names but implement setters) that call `_notify(..., what_changed=(...,))`
* Add `set_bounds(min_val=..., max_val=..., owner_token=...)` that updates both bounds *atomically* and fires exactly one notification with `what_changed` containing both (and `"value"` if clamped).

**B. Add `step`**

* Add `step: float` to `SmartParameter`.
* Default computed at creation; **do not** auto-recompute `step` when bounds later change.

This extends the current `SmartParameter` which only tracks `value` reactively.  

---

### 6) Plot model changes (parameter-aware compilation + constant broadcasting)

#### 6.1 Data fields to add to `Plot`

* `self._param_symbols: tuple[sympy.Symbol, ...]`
* `self._args: tuple[sympy.Symbol, ...]` (equal to `(symbol, *param_symbols)`)
* `self._func: Callable[..., Any]` compiled by `numpify(expr, args=self._args)`

This replaces the current single-argument compilation. 

#### 6.2 `compute_data(...)` changes

* Accept param values (either explicitly passed, or pulled from registry via controller).
* Call `y = func(x, *param_values)`.

**Constant/parameterized-constant broadcasting**
Before enforcing `x.shape == y.shape`, detect scalar `y` and broadcast:

* if `y_arr.ndim == 0`: `y_arr = numpy.full_like(x_arr, float(y_arr), dtype=float)`

This prevents the existing shape mismatch error for constant expressions. 

---

### 7) Dependency tracking + recompute-only-dependent-plots

#### 7.1 Data structures (on SmartFigure)

Maintain:

* `self._plots: OrderedDict[str, Plot]` (already exists)
* `self._plots_by_param: dict[sympy.Symbol, set[str]]`
* `self._param_callback_token: dict[sympy.Symbol, CallbackToken]` (for unregistering)
* `self._sliders_by_param: dict[sympy.Symbol, SmartSlider]` (UI layer, Stage 4)
* Optional convenience:

  * `self._plot_params: dict[str, tuple[sympy.Symbol,...]]`

#### 7.2 When plots are added/updated/removed

On create or update:

1. Analyze expression ⇒ `(symbol, param_symbols_sorted)`
2. Ensure registry contains those params (create if needed)
3. Update plot’s stored param list and compiled function
4. Update dependency mapping `plots_by_param`
5. Ensure parameter callbacks are registered for params used by this figure

On remove:

1. Remove plot from backend and `_plots`
2. Update dependency mapping for each param it used
3. If a param now has zero plots in this figure:

   * unregister this figure’s callback from that parameter (optional but recommended)
   * remove slider from **this figure’s UI** (Stage 4)
   * **do not** remove the parameter from the registry (retention policy)

#### 7.3 Parameter callback behavior

Figure registers one callback per parameter it uses:

* `param.register_callback(self._on_param_change)` (or per-param wrapper)

On notification:

* `affected_plots = self._plots_by_param[param_symbol]`
* recompute and update backend for those plots only

This satisfies “only plots depending on parameter”.

---

### 8) Figure UI policy for sliders (Option A)

* Each figure shows **only** sliders for parameters used by that figure’s current plots.
* If a plot is removed and a parameter becomes unused in that figure:

  * remove that slider from the figure UI
  * keep the parameter in the registry (never forget)

Implementation detail: `SmartFigure.widget` must build a container with both:

* a slider column/row (e.g. `VBox([...sliders...])`)
* the plotly `FigureWidget`

Currently it’s only `VBox([backend.fig])`. 

---

### 9) Binding sliders to parameters (two-way, no feedback loops)

#### 9.1 SmartSlider role

`SmartSlider` already has a main slider plus settings inputs for min/max/step. 
We will extend it into a controller bound to a `SmartParameter`.

#### 9.2 Two-way binding protocol

* When slider changes value:

  * call `param.set_protected(new_val, owner_token=slider_token, what_changed=("value",), source="slider")`
* When parameter changes (callback):

  * if `owner_token == slider_token`: ignore (it was the slider itself)
  * else update slider widget value/bounds in a “no-loop” way (e.g. temporary traitlet unobserve or just set if it won’t trigger a cycle)

#### 9.3 Bounds edits

When min/max fields change in the slider settings:

* call `param.set_bounds(min_val=..., max_val=..., owner_token=slider_token)`
* The parameter will clamp its value if needed and notify with `what_changed` including `"value"` when clamped.

#### 9.4 Step policy

* On auto-created parameters: `step=(max-min)/200`.
* On later bounds changes: do **not** auto-change `step`.
* (Optional) UI may still allow manual step edits; that is an explicit change, not an automatic one.

---

### 10) Documentation updates (must be explicit)

In docstrings / module docs, document:

* The exact symbol/parameter detection rules (including constants + parameterized constants)
* Per-figure slider policy (only used parameters)
* Registry retention policy: never forget parameters; cleanup is future work
* Deterministic ordering: params sorted by symbol name; `numpify(args=(symbol,*params))`
* Recompute-only-dependent-plots rule
* `what_changed` tuple semantics (including clamping behavior)

---

## OUTPUT PART 2 — Implementation stages

Below are 5 stages; the project remains usable after each stage.

---

### Stage 1 — Upgrade `SmartParameter` to support dynamic bounds + `what_changed` + `step`

**Description and instructions**

* Modify `SmartParameter`:

  * Add `step: float` stored on the parameter.
  * Make `min_val` and `max_val` into properties (backed by `_min_val/_max_val`) with setter logic:

    * validate bounds
    * clamp value if needed
    * notify once with `what_changed=("min",)` / `("max",)` plus `"value"` if clamped
  * Add `set_bounds(min_val=..., max_val=..., owner_token=...)`:

    * apply both updates and clamp if needed
    * send exactly one notification: `what_changed=("min","max")` plus `"value"` if clamped
* Ensure notifications pass `what_changed` as a tuple via kwargs to `_notify` (callbacks already accept kwargs flexibly). 

**Functional requirements**

* Value set notifies with `("value",)`.
* Bounds set notifies with tuples containing all changes, including `"value"` if clamped.
* `step` exists and does not auto-change when bounds change.

**Regression requirements**

* Existing callback system (weakrefs, idempotent registration) remains intact.
* Existing code that does `p.value = ...` continues to work.

**Completeness criteria**

* All Stage 1 cells in the notebook section “Stage 1 — SmartParameter contract” pass with green prints.

---

### Stage 2 — Expression analysis + parameter-aware Plot compilation + constant broadcasting

**Description and instructions**

* Replace `SmartFigure._resolve_symbol` with `analyze_expr` (or keep `_resolve_symbol` but broaden it) to implement:

  * constant expressions
  * 1-symbol default
  * 1-symbol + requested different ⇒ parameterized constant
  * > 1 symbols ⇒ must specify symbol
* Extend `Plot`:

  * store `param_symbols` and compile with `numpify(expr, args=(symbol, *param_symbols))`
* Extend `Plot.compute_data`:

  * accept param values
  * broadcast scalar y to match x before shape check

**Functional requirements**

* Constant expressions plot successfully.
* Parameterized constants plot successfully (no error).
* Multi-symbol expressions require explicit `symbol`.

**Regression requirements**

* Existing single-symbol plots behave as before.
* Existing multi-symbol error still happens when `symbol` is omitted.

**Completeness criteria**

* Notebook “Stage 2 — Symbol selection and parameter detection” passes.

---

### Stage 3 — Registry integration + deterministic parameter ordering + evaluation from registry

**Description and instructions**

* Add `parameter_registry` to `SmartFigure` and class-level default registry.
* On `fig.plot(...)`:

  * analyze expression to get params
  * ensure parameters exist in registry with defaults (including step)
  * store param ordering on plot
* On evaluation:

  * pull parameter values from registry in stored order and pass to compiled function

**Functional requirements**

* Parameters are created/reused in registry.
* Parameter ordering is deterministic (alphabetical by name).
* Changing registry values changes computed y-values.

**Regression requirements**

* Plot creation/updates that don’t introduce parameters behave unchanged.

**Completeness criteria**

* Notebook “Stage 3 — Registry integration and deterministic ordering” passes.

---

### Stage 4 — Recompute-only-dependent-plots + per-figure dependency tracking

**Description and instructions**

* On SmartFigure:

  * maintain `plots_by_param`
  * register callbacks on parameters used by this figure
* On parameter change:

  * recompute only dependent plots and update backend traces

**Functional requirements**

* Changing `a` updates plots that depend on `a` and does not change unrelated plots.

**Regression requirements**

* Figures without parameters still work.
* Updating a plot’s expression correctly updates dependencies.

**Completeness criteria**

* Notebook “Stage 4 — Recompute isolation” passes.

---

### Stage 5 — Figure slider UI (Option A) + slider removal-on-unused + registry retention

**Description and instructions**

* Change `SmartFigure.widget` to include sliders + plot widget (instead of only the backend fig). 
* Create sliders for parameters used by this figure only.
* When a plot is removed and a parameter becomes unused by this figure:

  * remove the slider from this figure UI
  * unregister callbacks for that parameter (recommended)
  * **do not remove parameter from registry** (retention policy)

**Functional requirements**

* Figure shows sliders only for its used parameters.
* Removing last plot using param removes slider from UI.
* Registry still contains param after slider removal.

**Regression requirements**

* UI still renders in JupyterLab as before (just with added sliders).
* Backend plotting remains correct.

**Completeness criteria**

* Notebook “Stage 5 — Figure slider UI policy” passes, and manual visual inspection looks correct.
