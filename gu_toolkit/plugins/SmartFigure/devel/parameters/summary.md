## Final consolidated requirements summary

### 1) Goal

Enable `SmartFigure` plots whose data depends on **parameters** detected from a SymPy expression. Parameters are controlled by sliders and updates recompute only the affected plots.

---

### 2) Symbol and parameter detection

Let `S = expr.free_symbols`.

**Independent variable (`symbol`) selection**

* If `|S| > 1`: user **must** pass `symbol=...` (the independent variable).
* If `|S| = 1`:

  * If `symbol` is **not specified**: that single symbol is the independent variable.
  * If `symbol` **is specified** and is **different** from the single free symbol: treat the expression as a **parameterized constant** in `symbol` (constant w.r.t. the independent variable; the single free symbol is a parameter).
* If `|S| = 0`: treat as a **constant** expression.

**Parameters**

* All free symbols other than the independent `symbol` are parameters.

---

### 3) Registry integration

**Registry selection**

* `SmartFigure` has a **class-level default** parameter registry (static property).
* If a figure is created with `parameter_registry=...`, it uses that registry instead.

**Parameter creation / reuse**

* For every newly encountered parameter symbol:

  * If already in the registry: reuse it.
  * Otherwise create it with defaults:

    * `value = 0`
    * `min = -1`, `max = 1`
    * `step = (max - min) / 200`

**Retention policy**

* **Never remove parameters from the registry**, even if no current plot uses them.
* Document this as an intentional choice; potential future work may introduce registry cleanup policies.

---

### 4) Figure UI policy for sliders

* Each `SmartFigure` displays **only sliders for parameters used by that figure’s current plots** (Option A).
* If a plot is removed and a parameter is no longer used by any plot in that figure:

  * **remove the parameter’s slider from the figure UI**
  * **do not remove the parameter from the registry** (per retention policy)
* We are **not** implementing the alternative where figures dynamically add sliders when other figures introduce new parameters.

---

### 5) Deterministic parameter ordering and numpify contract

For each plot:

* Remember:

  * independent variable `symbol`
  * the remaining parameter symbols ordered **alphabetically by symbol name**
* When compiling via `numpify`, supply explicit argument order:

  * `args = (symbol, *params_sorted_alphabetically)`
    This guarantees consistent call signatures and evaluation ordering.

---

### 6) Data generation for parameterized plots

* When evaluating a plot’s numpified function, plug in:

  * the sampled x-values for `symbol`
  * parameter values obtained from the registry (in the deterministic order above)

---

### 7) Recompute behavior on slider changes

* When a slider changes a parameter value:

  * recompute **only** the plots whose expressions depend on that parameter (and update their data)
  * do **not** recompute unrelated plots

---

### 8) SmartParameter dynamic properties and callbacks

`SmartParameter` must treat `value`, `min`, and `max` as **dynamic** properties whose changes notify observers.

**Callback signature behavior**

* The callback receives `what_changed` as a **tuple** listing *all* changes that occurred in the operation, e.g.:

  * `("value",)`
  * `("min","max")`
  * `("max","value")` if adjusting `max` clamps `value`

**Clamping rule**

* If changing `min/max` causes the current value to become out of bounds, `value` is clamped, and `what_changed` must include `"value"` in addition to the bound(s) changed.

---

### 9) Step policy

* `step` is set at creation to `(max - min) / 200` unless the registry already specifies it.
* After creation, `step` **stays unchanged** even if `min/max` later change.

---

### 10) Documentation requirements

* Document:

  * the parameter detection rules (including constants and parameterized constants)
  * the per-figure slider policy (only relevant parameters)
  * the “registry never forgets parameters” retention policy and that cleanup is future work
  * deterministic ordering and explicit `numpify(args=...)` behavior
  * recompute-only-dependent-plots rule
  * `what_changed` tuple semantics, including multi-change updates and clamping behavior
