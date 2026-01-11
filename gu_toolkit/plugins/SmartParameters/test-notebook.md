
## OUTPUT PART 3 — Comprehensive JupyterLab test cells

> Assumption: implementation lives in `smart_parameters.py` in the notebook directory.

### Cell 1 — Imports

```python
import gc
import warnings

import sympy as sp

from smart_parameters import (
    SmartParameter,
    SmartParameterRegistry,
    CallbackToken,
)
```

---

### Cell 2 — Defaults, coercion, clamping, unbounded bounds

```python
a = sp.Symbol('a')
p = SmartParameter(id=a)

assert p.id == a
assert p.type is float
assert p.min_val == -1
assert p.max_val == 1
assert p.default_val == 0

# Recommended init policy: value defaults to default_val when constructor value=None
assert p.value == 0

# Coercion
p.value = "0.25"
assert isinstance(p.value, float)
assert p.value == 0.25

# Clamping
p.value = 10
assert p.value == 1.0
p.value = -10
assert p.value == -1.0

# Unbounded above
p2 = SmartParameter(id=sp.Symbol('b'), max_val=None)
p2.value = 1e6
assert p2.value == 1e6

# Unbounded below
p3 = SmartParameter(id=sp.Symbol('c'), min_val=None)
p3.value = -1e6
assert p3.value == -1e6
```

---

### Cell 3 — Bounds validation

```python
try:
    SmartParameter(id=sp.Symbol('bad'), min_val=2, max_val=1)
    raise AssertionError("Expected ValueError for invalid bounds")
except ValueError:
    pass
```

---

### Cell 4 — Always notify (even if unchanged)

```python
p = SmartParameter(id=sp.Symbol('x'))
calls = []

def cb(param, **kwargs):
    calls.append((param.value, kwargs.get("owner_token")))

tok = p.register_callback(cb)

p.value = 0.0
p.value = 0.0
p.value = 0.0

assert len(calls) == 3, calls
assert calls[0][1] is None and calls[1][1] is None and calls[2][1] is None
```

---

### Cell 5 — Token idempotency via scan and removal

```python
p = SmartParameter(id=sp.Symbol('y'))
calls = []

def cb(param, **kwargs):
    calls.append(1)

t1 = p.register_callback(cb)
t2 = p.register_callback(cb)
assert t1 == t2, (t1, t2)

p.value = 0.1
assert len(calls) == 1

p.remove_callback(t1)
p.value = 0.2
assert len(calls) == 1  # no new calls

# removing again should be no-op
p.remove_callback(t1)
```

---

### Cell 6 — set_protected excludes exactly the owner token

```python
p = SmartParameter(id=sp.Symbol('z'))
log = []

def cb1(param, **kwargs):
    log.append(("cb1", kwargs.get("owner_token")))

def cb2(param, **kwargs):
    log.append(("cb2", kwargs.get("owner_token")))

t1 = p.register_callback(cb1)
t2 = p.register_callback(cb2)

p.set_protected(0.3, owner_token=t1, reason="slider1")

# cb1 excluded, cb2 called
assert ("cb1", t1) not in log
assert ("cb2", t1) in log

log.clear()
p.value = 0.4
assert ("cb1", None) in log and ("cb2", None) in log
```

---

### Cell 7 — Optional compatibility: callback(param) only

If you implement the “fallback to callback(param)” behavior, this should pass.

```python
p = SmartParameter(id=sp.Symbol('sig'))
called = []

def old_style(param):
    called.append(param.value)

t_old = p.register_callback(old_style)

# Excluding old_style means it won't be called
p.set_protected(0.12, owner_token=t_old, anything="ok")
assert called == []

# Use a different, real token so exclusion does not apply
def dummy(param, **kwargs):
    pass

t_dummy = p.register_callback(dummy)

p.set_protected(0.34, owner_token=t_dummy, anything="ok")
assert called == [0.34]
```

> If you decide to *require* callbacks accept `**kwargs`, delete this cell and document that requirement.

---

### Cell 8 — Aggregated errors: continue + warn once + store details

```python
p = SmartParameter(id=sp.Symbol('err'))
ran = []

def good(param, **kwargs):
    ran.append("good")

def bad1(param, **kwargs):
    raise RuntimeError("bad1 failed")

def bad2(param, **kwargs):
    raise ValueError("bad2 failed")

p.register_callback(good)
p.register_callback(bad1)
p.register_callback(bad2)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    p.value = 0.5

assert "good" in ran

# One warning per notify batch (recommended)
assert len(w) == 1, [str(x.message) for x in w]

errs = getattr(p, "last_callback_errors", None)
assert errs is not None and len(errs) == 2, errs
for e in errs:
    assert hasattr(e, "traceback")
    assert isinstance(e.traceback, str) and len(e.traceback) > 0
```

---

### Cell 9 — Weakref cleanup for bound methods (rerun-cell scenario)

```python
p = SmartParameter(id=sp.Symbol('weak'))

class Owner:
    def __init__(self):
        self.count = 0
    def cb(self, param, **kwargs):
        self.count += 1

o = Owner()
tok = p.register_callback(o.cb)

p.value = 0.1
assert o.count == 1

# Drop owner and force GC; callback should become dead
del o
gc.collect()

# Should not crash; dead callback should be cleaned on notify
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    p.value = 0.2

# No callback errors expected from a dead callback; it should be skipped.
assert getattr(p, "last_callback_errors", []) == []
```

---

### Cell 10 — Weakref requirement for non-weakrefable callbacks (optional)

This behavior can vary by Python build; treat as informational.

```python
p = SmartParameter(id=sp.Symbol('nw'))

try:
    p.register_callback(len)
    print("len was weakref-able here; ok.")
except TypeError:
    print("len not weakref-able; TypeError as expected.")
```

---

### Cell 11 — Registry auto-vivify and convenience methods

```python
reg = SmartParameterRegistry()

a = sp.Symbol('a')
pa = reg[a]  # auto-create

assert isinstance(pa, SmartParameter)
assert pa.id == a
assert pa.value == 0

# same object returned for same key
assert reg[a] is pa

# set_value clamps by default bounds
reg.set_value(a, 2.0)
assert reg[a].value == 1.0

log = []
def cb(param, **kwargs):
    log.append(kwargs.get("owner_token"))

tok = reg[a].register_callback(cb)
reg.set_protected(a, -2.0, owner_token=tok)
assert log == []           # excluded
assert reg[a].value == -1.0
```

---

### Cell 12 — Registry overwrite and deletion semantics

```python
reg = SmartParameterRegistry()
x = sp.Symbol('x')

p = reg[x]
assert reg[x] is p

p2 = SmartParameter(id=x, min_val=None, max_val=None, default_val=7)
reg[x] = p2
assert reg[x] is p2
assert reg[x].value == 7

del reg[x]
p3 = reg[x]  # auto-vivify fresh
assert p3 is not p2
assert p3.default_val == 0
```

---

### Cell 13 — Multi-controller “no loop” pattern (logic-only)

```python
p = SmartParameter(id=sp.Symbol('A'))

view1 = {"value": None}
view2 = {"value": None}

def update_view1(param, **kwargs):
    view1["value"] = param.value

def update_view2(param, **kwargs):
    view2["value"] = param.value

t_view1 = p.register_callback(update_view1)
t_view2 = p.register_callback(update_view2)

def controller1_set(new_val):
    p.set_protected(new_val, owner_token=t_view1, source="controller1")

def controller2_set(new_val):
    p.set_protected(new_val, owner_token=t_view2, source="controller2")

controller1_set(0.8)
assert view1["value"] is None   # excluded
assert view2["value"] == 0.8

controller2_set(-10)
assert view1["value"] == -1.0
assert view2["value"] == 0.8    # excluded; may be stale by design
```
