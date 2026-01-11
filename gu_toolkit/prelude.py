from __future__ import annotations

__all__=[]
# --- The deliberate classroom prelude ---
import sympy as sp
__all__+="sp"
__all__+= list(getattr(sp, "__all__", []))
import numpy as np
__all__+="np"

# Standard symbols (override/define explicitly for consistency)
x, y, z, t = sp.symbols("x y z t")
__all__+=["x","y","z","t"]
k, l, m, n = sp.symbols("k l m n", integer=True)
__all__+=["k","l","m","n"]
f, g, h = sp.symbols("f g h", cls=sp.Function)
__all__+=["f","g","h"]
