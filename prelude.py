from __future__ import annotations

__all__=[]
# --- The deliberate classroom prelude ---
import sympy as sp
__all__+=["sp"]
from sympy import *
__all__+= list(getattr(sp, "__all__", []))
import numpy as np
__all__+=["np"]

import pandas as pd
__all__+=["pd"]

# print("__all__ (from prelude):",__all__)
import sympy as sp

class SymbolFamily(sp.Symbol):
    """
    A SymPy Symbol that creates indexed children via [].
    Inherits from sp.Symbol, so all math (x**2, diff, etc.) works natively.
    """
    def __new__(cls, name, **kwargs):
        # Create the actual SymPy Symbol
        obj = super().__new__(cls, name, **kwargs)
        
        # Attach our family-specific attributes to the new instance
        # We use distinct names (e.g., _family_cache) to avoid colliding with SymPy internals
        obj._family_cache = {}
        obj._family_kwargs = kwargs
        return obj

    def __getitem__(self, k):
        if not isinstance(k, tuple):
            k = (k,)
            
        if k not in self._family_cache:
            sub = ",".join(map(str, k))
            child_name = f"{self.name}_{sub}"
            # Create a standard Symbol for the child
            self._family_cache[k] = sp.Symbol(child_name, **self._family_kwargs)
            
        return self._family_cache[k]

class FunctionFamily:
    """
    A wrapper for SymPy Functions (e.g., f(x)).
    SymPy Functions are complex to subclass directly, so this proxy 
    is the standard way to handle them.
    """
    def __init__(self, name, **kwargs):
        self.name = name
        self._kwargs = kwargs
        # Create the base function (e.g. f)
        self._base = sp.Function(name, **kwargs)
        self._cache = {}

    def __getitem__(self, k):
        if not isinstance(k, tuple):
            k = (k,)
        if k not in self._cache:
            sub = ",".join(map(str, k))
            # Create a new Function for the child (e.g. f_1)
            self._cache[k] = sp.Function(f"{self.name}_{sub}", **self._kwargs)
        return self._cache[k]

    def __call__(self, *args):
        # Allows f(x) to work
        return self._base(*args)
    
    def _sympy_(self):
        # Allows SymPy to recognize this object
        return self._base
    
    def __str__(self):
        return str(self._base)
    
    def __repr__(self):
        return repr(self._base)

__all__ += ["SymbolFamily", "FunctionFamily"]

# -----------------------
# Roman (lowercase)
# -----------------------
for _ch in "abcdefghijklmnopqrstuvwxyz":
    globals()[_ch] = SymbolFamily(_ch)

# conventional function letters
for _ch in "fgh":
    globals()[_ch] = FunctionFamily(_ch)

# conventional integer indices (as in your original snippet)
for _ch in "klmnij":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

__all__ += list("abcdefghijklmnopqrstuvwxyz")

# -----------------------
# Roman (uppercase)
# -----------------------
for _ch in "ABCDEFGHIJKLOPQRSTUVWXYZ":
    globals()[_ch] = SymbolFamily(_ch)

for _ch in "MN":
    globals()[_ch] = SymbolFamily(_ch, integer=True)

# conventional function letters
for _ch in "FGH":
    globals()[_ch] = FunctionFamily(_ch)

__all__ += list("ABCDEFGHJKLMNOPQRSTUVWXYZ")

# -----------------------
# Greek (lowercase): SymPy canonical names (not LaTeX macros)
# -----------------------
alpha = SymbolFamily("alpha")
beta = SymbolFamily("beta")
gamma = SymbolFamily("gamma")
delta = SymbolFamily("delta")

epsilon = SymbolFamily("epsilon")
varepsilon = SymbolFamily("varepsilon")

zeta = SymbolFamily("zeta")
eta = SymbolFamily("eta")

theta = SymbolFamily("theta")
vartheta = SymbolFamily("vartheta")

kappa = SymbolFamily("kappa")
lam = SymbolFamily("lambda")  # "lambda" is a Python keyword
mu = SymbolFamily("mu")
nu = SymbolFamily("nu")
xi = SymbolFamily("xi")

rho = SymbolFamily("rho")

sigma = SymbolFamily("sigma")
varsigma = SymbolFamily("varsigma")
tau = SymbolFamily("tau")

phi = SymbolFamily("phi")
varphi = SymbolFamily("varphi")

chi = SymbolFamily("chi")
psi = SymbolFamily("psi")
omega = SymbolFamily("omega")

__all__ += [
    "alpha","beta","gamma","delta",
    "epsilon","varepsilon",
    "zeta","eta",
    "theta","vartheta",
    "kappa","lam","mu","nu","xi","rho",
    "sigma","varsigma","tau",
    "phi","varphi",
    "chi","psi","omega",
]

del _ch





class Infix:
    """Generic infix operator used as: a |OP| b."""
    __slots__ = ("func",)

    def __init__(self, func):
        self.func = func

    def __ror__(self, left):
        return _InfixPartial(self.func, left)


class _InfixPartial:
    __slots__ = ("func", "left")

    def __init__(self, func, left):
        self.func = func
        self.left = left

    def __or__(self, right):
        return self.func(self.left, right)

eq = Infix(sp.Eq)
lt = Infix(sp.Lt)
le = Infix(sp.Le)
gt = Infix(sp.Gt)
ge = Infix(sp.Ge)
__all__+=["Infix", "eq", "lt", "le", "gt", "ge"]

## Demo:
# x, y = sp.symbols("x y")
# expr1 = x + 1
# expr2 = 2*y

# print(expr1 | eq | expr2)      # Eq(x + 1, 2*y)
# print((x**2) | eq | (y**2))    # Eq(x**2, y**2)


from IPython.display import Latex 
__all__+=["Latex"]

from pprint import pprint
__all__+=["pprint"]